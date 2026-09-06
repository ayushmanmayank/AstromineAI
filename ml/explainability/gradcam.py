"""Grad-CAM explainability via Captum's LayerGradCam, for the ResNet-50 arm."""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from captum.attr import LayerGradCam


def generate_gradcam(
    model: nn.Module,
    target_layer: nn.Module,
    input_tensor: torch.Tensor,
    target_class: int,
) -> np.ndarray:
    """Return a (H, W) Grad-CAM heatmap (upsampled to input_tensor's spatial
    size, min-max normalized to [0, 1]) for one input.

    `input_tensor`: shape (1, C, H, W). `target_layer`: e.g. model.layer4
    for a torchvision ResNet-50.
    """
    if input_tensor.dim() != 4 or input_tensor.size(0) != 1:
        raise ValueError(f"Expected a single-image batch (1, C, H, W), got {tuple(input_tensor.shape)}")

    model.eval()
    gradcam = LayerGradCam(model, target_layer)
    attribution = gradcam.attribute(input_tensor, target=target_class)
    upsampled = nn.functional.interpolate(
        attribution, size=input_tensor.shape[-2:], mode="bilinear", align_corners=False
    )
    heatmap = upsampled.squeeze().detach().cpu().numpy()
    lo, hi = heatmap.min(), heatmap.max()
    if hi > lo:
        heatmap = (heatmap - lo) / (hi - lo)
    else:
        heatmap = np.zeros_like(heatmap)
    return heatmap
