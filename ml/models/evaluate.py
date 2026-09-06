"""
Evaluation: accuracy + Expected Calibration Error (ECE) for a trained
torch model (ResNet-50 / ViT-B) against a VestaDataset split.

Real, runnable code — never run against real labeled data (0 samples as
of Month 1, see docs/month1_log.md). Raises clearly on an empty split
rather than reporting a meaningless accuracy/ECE.
"""

from __future__ import annotations

import argparse
import logging
import sys

import numpy as np
import torch
import torch.nn.functional as F
import yaml
from torch.utils.data import DataLoader

from ml.data.dataset import CLASSES, VestaDataset
from ml.models import cnn_resnet, vit_model

logger = logging.getLogger("evaluate")


def expected_calibration_error(confidences: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> float:
    """Standard ECE: bin predictions by confidence, compare each bin's
    mean confidence to its actual accuracy, weight by bin size."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(confidences)
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (confidences > lo) & (confidences <= hi)
        if not np.any(mask):
            continue
        bin_acc = correct[mask].mean()
        bin_conf = confidences[mask].mean()
        ece += (mask.sum() / n) * abs(bin_acc - bin_conf)
    return float(ece)


def evaluate_model(model: torch.nn.Module, dataset: VestaDataset, device: str = "cpu") -> dict:
    if len(dataset) == 0:
        raise RuntimeError(
            f"VestaDataset(split={dataset.split!r}) has 0 samples — cannot evaluate. "
            f"See docs/month1_log.md."
        )
    loader = DataLoader(dataset, batch_size=16, shuffle=False)
    model = model.to(device).eval()

    all_confidences, all_correct = [], []
    with torch.no_grad():
        for images, labels, _region_ids in loader:
            images, labels = images.to(device).float(), labels.to(device)
            probs = F.softmax(model(images), dim=1)
            confidences, preds = probs.max(dim=1)
            all_confidences.append(confidences.cpu().numpy())
            all_correct.append((preds == labels).cpu().numpy())

    confidences = np.concatenate(all_confidences)
    correct = np.concatenate(all_correct)
    return {
        "n_samples": len(dataset),
        "accuracy": float(correct.mean()),
        "expected_calibration_error": expected_calibration_error(confidences, correct),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["resnet50", "vit_b"], required=True)
    parser.add_argument("--checkpoint", required=True, help="Path to a trained model state_dict (.pt)")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--split", default="test")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")

    with open(args.config, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    metadata_csv = f"{config['data']['metadata_dir']}/sample_metadata.csv"

    dataset = VestaDataset(metadata_csv, split=args.split)
    model = (cnn_resnet if args.model == "resnet50" else vit_model).build_model(num_classes=len(CLASSES))
    model.load_state_dict(torch.load(args.checkpoint, map_location="cpu"))

    metrics = evaluate_model(model, dataset)
    logger.info("Evaluation on split=%s: %s", args.split, metrics)
    return 0


if __name__ == "__main__":
    sys.exit(main())
