"""
Attention rollout explainability for the ViT-B arm (Abnar & Zuidema 2020).

STUB, as explicitly scoped for this pass: the math is real, but the hook
wiring to actually capture per-layer attention weights from a timm ViT-B
forward pass is not implemented. Do not call `attention_rollout()`'s
`attentions` argument with a guess — wire up real forward hooks first.

TODO (before this is usable):
  - Register a forward hook on each `blocks[i].attn` module in the timm
    ViT-B model that captures the softmax attention weights (shape
    (batch, heads, tokens, tokens)) during a real forward pass.
  - Collect those into `attentions: list[torch.Tensor]`, one per layer,
    in order, and pass them into `attention_rollout()` below.
  - timm's default ViT attention implementation may need
    `model.set_attn_mode` or a custom attention class swap to expose
    attention weights at all (recent timm versions use a fused/scaled-
    dot-product-attention path that doesn't retain them by default) —
    confirm which timm version's internals this needs against the
    installed version before wiring hooks.
"""

from __future__ import annotations

import numpy as np
import torch


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
