"""
Training entry point for the Month 1 proposal's 3-way model comparison
(baseline / ResNet-50 / ViT-B).

Real, runnable training loop — not a stub. Has never been run end-to-end
against real labeled data: as of Month 1 slice 3, VestaDataset has 0
usable samples in every split (see docs/month1_log.md). This script
checks that up front and exits with a clear message rather than "training"
on an empty dataset and reporting a meaningless 100%/0% accuracy.
"""

from __future__ import annotations

import argparse
import logging
import sys

import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader

from ml.data.dataset import CLASSES, VestaDataset
from ml.models import cnn_resnet, vit_model
from ml.models.baseline import evaluate_baseline, train_baseline

logger = logging.getLogger("train")


def _require_nonempty(dataset: VestaDataset) -> None:
    if len(dataset) == 0:
        raise RuntimeError(
            f"VestaDataset(split={dataset.split!r}) has 0 samples. Refusing to train "
            f"or evaluate on an empty split rather than silently producing meaningless "
            f"metrics. See docs/month1_log.md (Month 1 close-out: NO-GO, 0 surviving "
            f"image-spectrum pairs) for why, and what acquisition needs to change."
        )


def train_torch_model(model: nn.Module, train_ds: VestaDataset, val_ds: VestaDataset, epochs: int, lr: float, device: str):
    _require_nonempty(train_ds)
    _require_nonempty(val_ds)

    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=16, shuffle=False)

    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        for images, labels, _region_ids in train_loader:
            images, labels = images.to(device).float(), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * images.size(0)

        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for images, labels, _region_ids in val_loader:
                images, labels = images.to(device).float(), labels.to(device)
                preds = model(images).argmax(dim=1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)

        logger.info(
            "epoch %d/%d: train_loss=%.4f val_acc=%.4f",
            epoch + 1, epochs, total_loss / len(train_ds), correct / max(total, 1),
        )
    return model


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["baseline_logreg", "baseline_rf", "resnet50", "vit_b"], required=True)
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")

    with open(args.config, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    metadata_csv = f"{config['data']['metadata_dir']}/sample_metadata.csv"

    train_ds = VestaDataset(metadata_csv, split="train")
    val_ds = VestaDataset(metadata_csv, split="val")

    if args.model in ("baseline_logreg", "baseline_rf"):
        _require_nonempty(train_ds)
        model_type = "logreg" if args.model == "baseline_logreg" else "random_forest"
        model = train_baseline(train_ds, model_type=model_type)
        metrics = evaluate_baseline(model, val_ds)
        logger.info("Validation metrics: %s", metrics)
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = (cnn_resnet if args.model == "resnet50" else vit_model).build_model(num_classes=len(CLASSES))
        train_torch_model(model, train_ds, val_ds, epochs=args.epochs, lr=args.lr, device=device)

    return 0


if __name__ == "__main__":
    sys.exit(main())
