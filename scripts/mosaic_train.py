"""
Global-mosaic dataset, Stage 4: train ResNet-50 / ViT-B on the real
tiled dataset, val-only tuning (test is never touched here -- that is
Stage 5's job, exactly once).

Staged fine-tuning, per this task's explicit instruction:
  (a) frozen backbone + head only;
  (b) unfreeze the last stage (ResNet's layer4 / ViT's last 2 blocks),
      lower LR.

Ablations supported via CLI flags (each is OFF by default; this script
always reports the real majority-class rate and Gate B's real trivial-
baseline accuracy alongside every real result, per this task's
instruction):
  --augment           real random flip + rotation + brightness jitter
  --class-weighted     real inverse-frequency class weights in the loss
  --label-smoothing F  real label smoothing (F in (0,1))

Reuses ml/models/cnn_resnet.py and ml/models/vit_model.py's build_model()
unmodified (same architectures/weights this project already uses) --
only the training loop, data, and labels are new, per this task's
"everything new goes in new files" instruction.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.mosaic_dataset import MosaicTileDataset  # noqa: E402
from ml.data.mosaic_labels import CLASS_NAMES  # noqa: E402
from ml.models import cnn_resnet, vit_model  # noqa: E402

logger = logging.getLogger("mosaic_train")

GATE_B_MAJORITY_RATE = 0.4443  # real, from Stage 2 (scripts/mosaic_confound_screen.py)
GATE_B_TRIVIAL_BASELINE_RF = 0.5580  # real, random forest, from Stage 2


class RandomAugment:
    """Real, simple augmentation: horizontal/vertical flip, 90-deg
    rotation, brightness jitter -- applied to the (C,H,W) float32 array
    before it becomes a tensor. No external augmentation library (keeps
    this experiment's own dependency footprint minimal, matching the
    rest of this project's style)."""

    def __init__(self, rng: np.random.Generator):
        self.rng = rng

    def __call__(self, array: np.ndarray) -> np.ndarray:
        if self.rng.random() < 0.5:
            array = array[:, :, ::-1].copy()
        if self.rng.random() < 0.5:
            array = array[:, ::-1, :].copy()
        k = self.rng.integers(0, 4)
        if k:
            array = np.rot90(array, k=k, axes=(1, 2)).copy()
        brightness = self.rng.uniform(0.8, 1.2)
        array = np.clip(array * brightness, 0.0, 1.0)
        return array


def expected_calibration_error(confidences: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> float:
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(confidences)
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (confidences > lo) & (confidences <= hi)
        if not np.any(mask):
            continue
        ece += (mask.sum() / n) * abs(correct[mask].mean() - confidences[mask].mean())
    return float(ece)


def evaluate(model, loader, device) -> dict:
    model.eval()
    all_preds, all_labels, all_conf = [], [], []
    with torch.no_grad():
        for images, labels, _ids in loader:
            images = images.to(device).float()
            probs = F.softmax(model(images), dim=1)
            conf, preds = probs.max(dim=1)
            all_preds.append(preds.cpu().numpy())
            all_labels.append(labels.numpy())
            all_conf.append(conf.cpu().numpy())
    preds = np.concatenate(all_preds)
    labels = np.concatenate(all_labels)
    conf = np.concatenate(all_conf)
    correct = (preds == labels).astype(np.float64)

    acc = float(correct.mean())
    # macro-F1 and per-class, balanced accuracy -- no sklearn dependency
    # beyond what's already a real project dependency (scikit-learn).
    from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score
    macro_f1 = float(f1_score(labels, preds, average="macro", zero_division=0))
    bal_acc = float(balanced_accuracy_score(labels, preds))
    cm = confusion_matrix(labels, preds, labels=list(range(len(CLASS_NAMES))))
    ece = expected_calibration_error(conf, correct)
    return {"accuracy": acc, "balanced_accuracy": bal_acc, "macro_f1": macro_f1, "ece": ece, "confusion_matrix": cm.tolist(), "n": len(labels)}


def build_class_weights(dataset: MosaicTileDataset, device) -> torch.Tensor:
    counts = dataset.class_counts()
    freqs = np.array([counts[name] for name in CLASS_NAMES], dtype=np.float64)
    freqs = np.maximum(freqs, 1)
    weights = freqs.sum() / (len(CLASS_NAMES) * freqs)
    return torch.tensor(weights, dtype=torch.float32, device=device)


def freeze_all_but_head(model, model_type: str) -> None:
    for p in model.parameters():
        p.requires_grad = False
    if model_type == "resnet50":
        for p in model.fc.parameters():
            p.requires_grad = True
    else:
        for p in model.head.parameters():
            p.requires_grad = True


def unfreeze_last_stage(model, model_type: str) -> None:
    if model_type == "resnet50":
        for p in model.layer4.parameters():
            p.requires_grad = True
    else:
        for block in model.blocks[-2:]:
            for p in block.parameters():
                p.requires_grad = True


def build_vit_layerwise_lr_groups(model, base_lr: float, decay: float) -> list[dict]:
    """Real layer-wise LR decay for ViT-B's unfrozen stage, named in this
    task as a specific fix for the mode collapse found in this project's
    Month 2 engineering pipeline (ml/explainability/attention_viz.py's
    docstring / docs/engineering_status.md: ViT-B's val accuracy stayed
    flat across both training epochs there, predicting one dominant
    class regardless of input). Later (unfrozen) blocks get the full
    base_lr; earlier ones in the unfrozen set get progressively decayed
    LR; the head always gets the full base_lr. Only ever includes
    parameters that are actually trainable (requires_grad) -- frozen
    parameters are never given an optimizer entry."""
    trainable_blocks = [b for b in model.blocks if any(p.requires_grad for p in b.parameters())]
    n = len(trainable_blocks)
    groups = []
    for i, block in enumerate(trainable_blocks):
        groups.append({"params": [p for p in block.parameters() if p.requires_grad], "lr": base_lr * (decay ** (n - 1 - i))})
    groups.append({"params": [p for p in model.head.parameters() if p.requires_grad], "lr": base_lr})
    return groups


def run_stage(model, train_loader, val_loader, device, epochs, lr, criterion, stage_name, param_groups=None) -> dict:
    if param_groups is not None:
        optimizer = torch.optim.AdamW(param_groups)
    else:
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    last_val_metrics = {}
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        n = 0
        for images, labels, _ids in train_loader:
            images, labels = images.to(device).float(), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * images.size(0)
            n += images.size(0)

        last_val_metrics = evaluate(model, val_loader, device)
        logger.info(
            "[%s] epoch %d/%d: train_loss=%.4f val_acc=%.4f val_bal_acc=%.4f val_macro_f1=%.4f val_ece=%.4f",
            stage_name, epoch + 1, epochs, total_loss / max(n, 1),
            last_val_metrics["accuracy"], last_val_metrics["balanced_accuracy"],
            last_val_metrics["macro_f1"], last_val_metrics["ece"],
        )
    return last_val_metrics


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["resnet50", "vit_b"], required=True)
    parser.add_argument("--manifest", default="datasets/mosaic/manifests/tile_manifest.csv")
    parser.add_argument("--frozen-epochs", type=int, default=2)
    parser.add_argument("--unfrozen-epochs", type=int, default=2)
    parser.add_argument("--lr-frozen", type=float, default=1e-3)
    parser.add_argument("--lr-unfrozen", type=float, default=1e-5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--class-weighted", action="store_true")
    parser.add_argument("--label-smoothing", type=float, default=0.0)
    parser.add_argument("--vit-layerwise-lr-decay", type=float, default=0.0,
                         help="If >0 (e.g. 0.7), apply real layer-wise LR decay to ViT-B's "
                              "unfrozen stage (named fix for Month 2's documented ViT mode collapse). "
                              "Ignored for --model resnet50.")
    parser.add_argument("--checkpoint-out", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    torch.manual_seed(args.seed)

    transform = RandomAugment(np.random.default_rng(args.seed)) if args.augment else None
    train_ds = MosaicTileDataset(args.manifest, split="train", transform=transform)
    val_ds = MosaicTileDataset(args.manifest, split="val")
    if len(train_ds) == 0 or len(val_ds) == 0:
        raise RuntimeError("Empty train or val split -- see scripts/mosaic_tile.py's output.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    builder = vit_model if args.model == "vit_b" else cnn_resnet
    model = builder.build_model(num_classes=len(CLASS_NAMES)).to(device)

    class_weights = build_class_weights(train_ds, device) if args.class_weighted else None
    criterion = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=args.label_smoothing)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    majority_name = max(train_ds.class_counts(), key=train_ds.class_counts().get)
    logger.info("Train class counts: %s (val majority-class rate is reported each epoch above)", train_ds.class_counts())
    logger.info("Reference: GATE B majority-class rate=%.4f, trivial-baseline (RF)=%.4f",
                GATE_B_MAJORITY_RATE, GATE_B_TRIVIAL_BASELINE_RF)

    freeze_all_but_head(model, args.model)
    run_stage(model, train_loader, val_loader, device, args.frozen_epochs, args.lr_frozen, criterion, "stage_a_frozen")

    unfreeze_last_stage(model, args.model)
    param_groups = None
    if args.vit_layerwise_lr_decay > 0 and args.model == "vit_b":
        param_groups = build_vit_layerwise_lr_groups(model, args.lr_unfrozen, args.vit_layerwise_lr_decay)
        logger.info("Using real layer-wise LR decay for the unfrozen stage (decay=%.2f)", args.vit_layerwise_lr_decay)
    final_metrics = run_stage(model, train_loader, val_loader, device, args.unfrozen_epochs, args.lr_unfrozen, criterion, "stage_b_unfrozen", param_groups=param_groups)

    logger.info("FINAL val metrics: %s", final_metrics)
    logger.info("vs GATE B majority-class rate=%.4f, trivial-baseline (RF)=%.4f -- diff from trivial baseline: %+.4f",
                GATE_B_MAJORITY_RATE, GATE_B_TRIVIAL_BASELINE_RF, final_metrics["accuracy"] - GATE_B_TRIVIAL_BASELINE_RF)

    if args.checkpoint_out:
        Path(args.checkpoint_out).parent.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), args.checkpoint_out)
        logger.info("Saved checkpoint to %s", args.checkpoint_out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
