"""ViT-B (Month 1 proposal's 3-way comparison, arm 3 of 3), via timm."""

from __future__ import annotations

import timm
import torch.nn as nn


def build_model(num_classes: int, pretrained: bool = True) -> nn.Module:
    return timm.create_model("vit_base_patch16_224", pretrained=pretrained, num_classes=num_classes)
