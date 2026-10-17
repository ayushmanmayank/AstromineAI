"""
Attention rollout explainability for the ViT-B arm (Abnar & Zuidema 2020).

Month 2 (Slice: engineering pipeline) update: the hook wiring described in
the TODO below (previously unimplemented) is now real. `attention_rollout()`
itself was already correct math, unchanged here; `capture_vit_attentions()`
and `vit_attention_rollout()` are new.

What confirming the TODO actually required, checked against the installed
timm version (1.0.29) rather than assumed:
  - `timm.layers.attention.Attention.forward()` takes a `fused_attn: bool`
    fast path by default (`F.scaled_dot_product_attention`), which computes
    attention internally without ever materializing/returning the (batch,
    heads, tokens, tokens) weight matrix — confirmed by reading its real
    source (`inspect.getsource`) before writing anything here, exactly the
    risk this module's docstring had already flagged.
  - A plain `register_forward_hook` cannot see it either way: the module's
    `forward()` returns only the final projected output, never the
    intermediate attention weights, fused path or not.
  - The fix: temporarily monkey-patch each `block.attn.forward` (bound
    method swap, restored via try/finally so a model is never left
    mutated after use — safe to call repeatedly against a long-lived
    model instance, e.g. from the backend) with a faithful reimplementation
    of the manual (non-fused) computation path, which stashes the softmax
    attention weights into a shared list before returning the normal
    output. Verified end-to-end against a real (untrained, randomly
    initialized) `vit_base_patch16_224`: captures exactly 12 real
    (1, 12, 197, 197) attention tensors (12 layers, 12 heads, 196 patches
    + 1 CLS token) from one real forward pass, output shape/values
    unaffected, and the original `forward` is confirmed restored
    afterward.
  - This reimplementation only covers the plain-inference call shape this
    project ever actually uses (no `attn_mask`, no causal masking) — it
    does not reproduce the mask-handling branches of the real forward,
    since those paths are never exercised here.
"""

from __future__ import annotations

import types
from contextlib import contextmanager

import numpy as np
import torch
import torch.nn as nn


def attention_rollout(attentions: list[torch.Tensor], discard_ratio: float = 0.9) -> np.ndarray:
    """Combine per-layer attention matrices into a single rollout map
    (Abnar & Zuidema 2020: multiply attention matrices across layers,
    adding a residual/identity term per layer to account for skip
    connections, then read off the CLS token's attention to all patches).

    `attentions`: list of (batch, heads, tokens, tokens) tensors, one per
    transformer layer, in forward-pass order. This function's math is
    implemented and correct given real attention tensors — it has never
    been run against real ones, since the hook wiring to produce them
    (see module docstring TODO) doesn't exist yet.

    Returns a (batch, tokens-1) numpy array: rollout attention from the
    CLS token to each patch token (CLS-to-CLS excluded).
    """
    if not attentions:
        raise ValueError("attention_rollout() called with an empty attentions list")

    result = None
    for attn in attentions:
        # Average over heads, then discard the lowest-attention fraction
        # per row before renormalizing (standard rollout noise reduction).
        attn_avg = attn.mean(dim=1)  # (batch, tokens, tokens)
        flat = attn_avg.reshape(attn_avg.size(0), -1)
        n_discard = int(flat.size(1) * discard_ratio)
        if n_discard > 0:
            threshold = flat.topk(flat.size(1) - n_discard, dim=1, largest=True).values[:, -1]
            attn_avg = torch.where(attn_avg >= threshold.view(-1, 1, 1), attn_avg, torch.zeros_like(attn_avg))

        identity = torch.eye(attn_avg.size(-1), device=attn_avg.device).unsqueeze(0)
        attn_with_residual = 0.5 * attn_avg + 0.5 * identity
        attn_with_residual = attn_with_residual / attn_with_residual.sum(dim=-1, keepdim=True)

        result = attn_with_residual if result is None else torch.matmul(attn_with_residual, result)

    cls_to_patches = result[:, 0, 1:]  # CLS token's rollout attention to every patch token
    return cls_to_patches.detach().cpu().numpy()


def _make_capturing_forward(store: list[torch.Tensor]):
    """Return a bound-method-compatible forward that reimplements timm
    Attention's manual (non-fused) computation path, appending the softmax
    attention weights to `store` before returning the normal output.
    Assumes attn_mask=None, is_causal=False (this project's only real call
    shape) — see module docstring."""

    def patched_forward(self, x: torch.Tensor, attn_mask=None, is_causal: bool = False) -> torch.Tensor:
        B, N, C = x.shape
        gate = self.gate(x).sigmoid() if self.gate is not None else None
        qkv = self.qkv(x).reshape(B, N, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv.unbind(0)
        q, k = self.q_norm(q), self.k_norm(k)

        q_scaled = q * self.scale
        attn = q_scaled @ k.transpose(-2, -1)
        attn = attn.softmax(dim=-1)
        attn = self.attn_drop(attn)
        store.append(attn.detach())
        x = attn @ v

        x = x.transpose(1, 2).reshape(B, N, self.attn_dim)
        x = self.norm(x)
        if gate is not None:
            x = x * gate
        x = self.proj(x)
        x = self.proj_drop(x)
        return x

    return patched_forward


@contextmanager
def capture_vit_attentions(model: nn.Module):
    """Context manager: temporarily monkey-patches every `blocks[i].attn`
    module's forward to capture its real softmax attention weights during
    whatever forward pass(es) happen inside the `with` block, then restores
    the original forward methods on exit (even if the block raises) — a
    model instance is never left mutated after use.

    Usage:
        with capture_vit_attentions(model) as attentions:
            output = model(input_tensor)
        rollout = attention_rollout(attentions)

    `attentions` is the same list object throughout — read it only after
    the forward pass(es) you care about have run inside the `with` block.
    """
    captured: list[torch.Tensor] = []
    originals: list[tuple[nn.Module, object]] = []
    patched_forward = _make_capturing_forward(captured)
    try:
        for block in model.blocks:
            originals.append((block.attn, block.attn.forward))
            block.attn.forward = types.MethodType(patched_forward, block.attn)
        yield captured
    finally:
        for attn_module, original_forward in originals:
            attn_module.forward = original_forward


def vit_attention_rollout(
    model: nn.Module,
    input_tensor: torch.Tensor,
    discard_ratio: float = 0.9,
) -> np.ndarray:
    """End-to-end convenience wrapper (mirrors gradcam.py's
    `generate_gradcam()` single-call style): runs one real forward pass of
    `model` (a timm ViT-B, e.g. built by ml/models/vit_model.build_model())
    on `input_tensor`, capturing real per-layer attention weights via
    `capture_vit_attentions()`, and returns the CLS-to-patch rollout map
    reshaped to the model's real patch grid (e.g. 14x14 for
    vit_base_patch16_224 at 224x224 input) as a 2D (H_patches, W_patches)
    array, min-max normalized to [0, 1] to match `generate_gradcam()`'s
    output convention.

    `input_tensor`: shape (1, C, H, W), same convention as
    ml/explainability/gradcam.py's generate_gradcam().
    """
    if input_tensor.dim() != 4 or input_tensor.size(0) != 1:
        raise ValueError(f"Expected a single-image batch (1, C, H, W), got {tuple(input_tensor.shape)}")

    model.eval()
    with capture_vit_attentions(model) as attentions, torch.no_grad():
        model(input_tensor)

    rollout = attention_rollout(attentions, discard_ratio=discard_ratio)  # (1, n_patches)
    n_patches = rollout.shape[1]
    grid_size = int(round(n_patches ** 0.5))
    if grid_size * grid_size != n_patches:
        raise ValueError(
            f"Rollout has {n_patches} patch tokens, not a perfect square — cannot reshape "
            f"to a 2D grid. This model's patch embedding grid may not be square."
        )
    heatmap = rollout[0].reshape(grid_size, grid_size)

    lo, hi = heatmap.min(), heatmap.max()
    if hi > lo:
        heatmap = (heatmap - lo) / (hi - lo)
    else:
        heatmap = np.zeros_like(heatmap)
    return heatmap
