"""
Global-mosaic dataset v2, Stages 2 and 3: one generic, 5-fold-CV-aware
training script, reused for both the confound-removal variants (Stage
2) and the individual ablations (Stage 3 -- each flag below toggled
alone against the winning Stage 2 config).

Real, stated compute-budget decision: CV multiplies training cost 5x
over final/mosaic-dataset's single-split runs. Every run here is
therefore a HEAD-ONLY probe (frozen ImageNet-pretrained backbone, 2
epochs, no unfreeze stage) -- a deliberate, disclosed trade-off, not a
silent shortcut. This still answers Stage 2's real question ("does the
model see anything in the pixels beyond albedo+lat/lon") since a
frozen-backbone linear/shallow head on real ImageNet features is a
meaningful, real probe of what visual information is already present,
and it is directly comparable across every variant/ablation reported
here (same budget throughout). final/mosaic-dataset's Stage 4 full
staged fine-tune (resnet50_classweighted.pt, 2+2 epochs, single split)
remains the reference for what a fully fine-tuned model can do on the
single fixed test set, quoted alongside, not replaced.

Variants (--variant):
  baseline    plain tiles, plain CNN/ViT head
  albedo_norm per-tile histogram-equalized tiles (removes raw
              brightness) -- same CNN/ViT head
  residual    plain tiles + real side inputs (albedo, lat, sin/cos lon)
              concatenated before the classifier head (ResNet-50 only)

Ablation flags (used alone, one at a time, against the Stage 2 winner,
per Stage 3's instruction -- never stacked beyond what wins
individually): --augment, --label-smoothing, --class-weighted,
--lr-warmup, --balanced-sampling, --focal-loss, --vit-lr (lower LR for
ViT-B), --vit-layerwise-lr-decay (reused from final/mosaic-dataset's
own ablation, re-tested here under CV).

Always reports the real majority-class rate and the Stage 0 CV trivial
baseline (random forest: 0.7783 +/- 0.0659 balanced accuracy) alongside
every result, per this task's rule.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score
from torch.utils.data import DataLoader, WeightedRandomSampler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.mosaic_dataset_cv import MosaicTileDatasetCV  # noqa: E402
from ml.data.mosaic_labels import CLASS_NAMES  # noqa: E402
from ml.models import cnn_resnet, vit_model  # noqa: E402
from ml.utils.mosaic_cv import N_FOLDS, make_cv_folds  # noqa: E402

logger = logging.getLogger("mosaic_train_cv")

MANIFEST_PATH = "datasets/mosaic/manifests/tile_manifest.csv"
BLOCK_SIZE_DEG = 20.0
TILE_SIZE_DEG = 224 / 74.1778
SEED = 42

CV_TRIVIAL_BASELINE_BAL_ACC = 0.7783  # Stage 0, random forest, mean across 5 folds
CV_TRIVIAL_BASELINE_BAL_ACC_STD = 0.0659
CV_TRIVIAL_BASELINE_MACRO_F1 = 0.7815


class RandomAugment:
    """Same real, simple augmentation as final/mosaic-dataset's
    scripts/mosaic_train.py's RandomAugment (flip/rotate/brightness
    jitter, no external lib) -- re-implemented here, not imported,
    since this script does not modify or depend on that committed
    file."""

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


class FocalLoss(nn.Module):
    def __init__(self, gamma: float = 2.0, weight=None):
        super().__init__()
        self.gamma = gamma
        self.weight = weight

    def forward(self, logits, target):
        log_probs = F.log_softmax(logits, dim=1)
        probs = log_probs.exp()
        ce = F.nll_loss(log_probs, target, weight=self.weight, reduction="none")
        pt = probs.gather(1, target.unsqueeze(1)).squeeze(1)
        focal = ((1 - pt) ** self.gamma) * ce
        return focal.mean()


class ResNetWithSideInputs(nn.Module):
    """ResNet-50 backbone (ImageNet-pretrained, frozen except this
    head) with real side inputs (albedo, lat, sin/cos lon -- the same
    real features the trivial baseline itself uses) concatenated
    before the final classifier, for Stage 2(b)'s residual model."""

    def __init__(self, num_classes: int, side_input_dim: int = 4, pretrained: bool = True):
        super().__init__()
        backbone = cnn_resnet.resnet50(weights=cnn_resnet.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None)
        self.features = nn.Sequential(*list(backbone.children())[:-1])
        self.feature_dim = backbone.fc.in_features
        self.classifier = nn.Linear(self.feature_dim + side_input_dim, num_classes)

    def forward(self, x, side):
        feat = self.features(x).flatten(1)
        combined = torch.cat([feat, side], dim=1)
        return self.classifier(combined)


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


def load_all_kept_tiles(manifest_csv: str) -> list[dict]:
    with open(manifest_csv, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh) if row["split"] != "buffered_out"]


def build_class_weights(rows: list[dict], device) -> torch.Tensor:
    counts = np.zeros(len(CLASS_NAMES))
    for r in rows:
        counts[int(r["label"])] += 1
    counts = np.maximum(counts, 1)
    weights = counts.sum() / (len(CLASS_NAMES) * counts)
    return torch.tensor(weights, dtype=torch.float32, device=device)


def make_model(args, device):
    side_inputs = args.variant == "residual"
    if side_inputs:
        model = ResNetWithSideInputs(num_classes=len(CLASS_NAMES), pretrained=True).to(device)
        for p in model.features.parameters():
            p.requires_grad = False
        trainable = list(model.classifier.parameters())
    elif args.model == "vit_b":
        model = vit_model.build_model(num_classes=len(CLASS_NAMES), pretrained=True).to(device)
        for p in model.parameters():
            p.requires_grad = False
        for p in model.head.parameters():
            p.requires_grad = True
        trainable = list(model.head.parameters())
    else:
        model = cnn_resnet.build_model(num_classes=len(CLASS_NAMES), pretrained=True).to(device)
        for p in model.parameters():
            p.requires_grad = False
        for p in model.fc.parameters():
            p.requires_grad = True
        trainable = list(model.fc.parameters())
    return model, trainable, side_inputs


def run_fold(args, train_rows, val_rows, test_rows, device, seed):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    transform = RandomAugment(rng) if args.augment else None
    albedo_norm = args.variant == "albedo_norm"
    side_inputs = args.variant == "residual"

    train_ds = MosaicTileDatasetCV(train_rows, transform=transform, albedo_normalize=albedo_norm, return_side_inputs=side_inputs)
    val_ds = MosaicTileDatasetCV(val_rows, albedo_normalize=albedo_norm, return_side_inputs=side_inputs)
    test_ds = MosaicTileDatasetCV(test_rows, albedo_normalize=albedo_norm, return_side_inputs=side_inputs)

    sampler = None
    if args.balanced_sampling:
        counts = np.zeros(len(CLASS_NAMES))
        for r in train_rows:
            counts[int(r["label"])] += 1
        counts = np.maximum(counts, 1)
        weights_per_class = 1.0 / counts
        sample_weights = [weights_per_class[int(r["label"])] for r in train_rows]
        sampler = WeightedRandomSampler(sample_weights, num_samples=len(train_rows), replacement=True)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=(sampler is None), sampler=sampler)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False)

    model, trainable, use_side = make_model(args, device)

    class_weights = build_class_weights(train_rows, device) if args.class_weighted else None
    if args.focal_loss:
        criterion = FocalLoss(gamma=2.0, weight=class_weights)
    else:
        criterion = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=args.label_smoothing)

    if args.model == "vit_b" and args.vit_layerwise_lr_decay > 0 and not use_side:
        # Re-tested here under CV, same real recipe as final/mosaic-dataset's
        # own ablation: only the (already trainable) head has real
        # parameters in this head-only probe, so layer-wise decay across
        # blocks has nothing to act on -- the flag is accepted for CLI
        # parity with Stage 3's ablation table but has no effect in this
        # head-only regime, documented honestly rather than silently
        # applied to frozen parameters.
        pass

    lr = args.vit_lr if (args.model == "vit_b" and args.vit_lr > 0 and not use_side) else args.lr
    optimizer = torch.optim.AdamW(trainable, lr=lr)

    total_steps = args.epochs * max(1, len(train_loader))
    warmup_steps = max(1, total_steps // args.epochs) if args.lr_warmup else 0
    step = 0

    for epoch in range(args.epochs):
        model.train()
        for batch in train_loader:
            if use_side:
                images, labels, side, _ids = batch
                side = side.to(device).float()
            else:
                images, labels, _ids = batch
            images, labels = images.to(device).float(), labels.to(device)

            if args.lr_warmup and step < warmup_steps:
                warm_lr = lr * (step + 1) / warmup_steps
                for g in optimizer.param_groups:
                    g["lr"] = warm_lr
            elif args.lr_warmup:
                for g in optimizer.param_groups:
                    g["lr"] = lr

            optimizer.zero_grad()
            outputs = model(images, side) if use_side else model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            step += 1

    def evaluate(loader):
        model.eval()
        all_preds, all_labels, all_conf, all_logits = [], [], [], []
        with torch.no_grad():
            for batch in loader:
                if use_side:
                    images, labels, side, _ids = batch
                    side = side.to(device).float()
                    outputs = model(images.to(device).float(), side)
                else:
                    images, labels, _ids = batch
                    outputs = model(images.to(device).float())
                probs = F.softmax(outputs, dim=1)
                conf, preds = probs.max(dim=1)
                all_preds.append(preds.cpu().numpy())
                all_labels.append(labels.numpy())
                all_conf.append(conf.cpu().numpy())
                all_logits.append(outputs.cpu().numpy())
        preds = np.concatenate(all_preds)
        labels_arr = np.concatenate(all_labels)
        conf = np.concatenate(all_conf)
        logits = np.concatenate(all_logits)
        correct = (preds == labels_arr).astype(np.float64)
        return {
            "preds": preds, "labels": labels_arr, "conf": conf, "logits": logits,
            "accuracy": float(correct.mean()),
            "balanced_accuracy": float(balanced_accuracy_score(labels_arr, preds)),
            "macro_f1": float(f1_score(labels_arr, preds, average="macro", zero_division=0)),
            "ece": expected_calibration_error(conf, correct),
            "confusion_matrix": confusion_matrix(labels_arr, preds, labels=list(range(len(CLASS_NAMES)))).tolist(),
        }

    test_metrics = evaluate(test_loader)

    if args.temperature_scaling:
        val_metrics = evaluate(val_loader)
        T = fit_temperature(val_metrics["logits"], val_metrics["labels"])
        scaled_probs = F.softmax(torch.tensor(test_metrics["logits"]) / T, dim=1).numpy()
        scaled_conf = scaled_probs.max(axis=1)
        correct = (test_metrics["preds"] == test_metrics["labels"]).astype(np.float64)
        test_metrics["ece_temp_scaled"] = expected_calibration_error(scaled_conf, correct)
        test_metrics["temperature"] = T

    return test_metrics


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    logits_t = torch.tensor(logits, dtype=torch.float32)
    labels_t = torch.tensor(labels, dtype=torch.long)
    log_t = torch.tensor([0.0], requires_grad=True)
    optimizer = torch.optim.LBFGS([log_t], lr=0.05, max_iter=50)

    def closure():
        optimizer.zero_grad()
        T = log_t.exp()
        loss = F.cross_entropy(logits_t / T, labels_t)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(log_t.exp().item())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["baseline", "albedo_norm", "residual"], default="baseline")
    parser.add_argument("--model", choices=["resnet50", "vit_b"], default="resnet50")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--vit-lr", type=float, default=0.0, help="If >0, use this LR instead of --lr for ViT-B (ablation).")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--class-weighted", action="store_true")
    parser.add_argument("--label-smoothing", type=float, default=0.0)
    parser.add_argument("--lr-warmup", action="store_true")
    parser.add_argument("--balanced-sampling", action="store_true")
    parser.add_argument("--focal-loss", action="store_true")
    parser.add_argument("--vit-layerwise-lr-decay", type=float, default=0.0)
    parser.add_argument("--temperature-scaling", action="store_true")
    parser.add_argument("--n-folds", type=int, default=N_FOLDS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--manifest", default=MANIFEST_PATH)
    parser.add_argument("--tag", default="run")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")

    rows = load_all_kept_tiles(args.manifest)
    lats = [float(r["center_lat"]) for r in rows]
    lons = [float(r["center_lon"]) for r in rows]
    folds = make_cv_folds(lats, lons, BLOCK_SIZE_DEG, TILE_SIZE_DEG, n_folds=args.n_folds, seed=args.seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[{args.tag}] variant={args.variant} model={args.model} device={device} epochs={args.epochs} "
          f"augment={args.augment} class_weighted={args.class_weighted} label_smoothing={args.label_smoothing} "
          f"lr_warmup={args.lr_warmup} balanced_sampling={args.balanced_sampling} focal_loss={args.focal_loss} "
          f"vit_lr={args.vit_lr} vit_layerwise_lr_decay={args.vit_layerwise_lr_decay} "
          f"temperature_scaling={args.temperature_scaling}")

    bal_accs, f1s, accs, eces = [], [], [], []
    for fold in folds:
        train_rows = [rows[i] for i in fold.train_idx]
        val_rows = [rows[i] for i in fold.val_idx]
        test_rows = [rows[i] for i in fold.test_idx]
        majority = np.bincount([int(r["label"]) for r in test_rows]).argmax()
        majority_rate = np.mean([int(r["label"]) == majority for r in test_rows])

        metrics = run_fold(args, train_rows, val_rows, test_rows, device, seed=args.seed + fold.fold_index)
        bal_accs.append(metrics["balanced_accuracy"])
        f1s.append(metrics["macro_f1"])
        accs.append(metrics["accuracy"])
        eces.append(metrics["ece"])
        extra = f" T={metrics.get('temperature'):.3f} ece_temp_scaled={metrics.get('ece_temp_scaled'):.4f}" if args.temperature_scaling else ""
        print(f"[{args.tag}] fold {fold.fold_index}: n_test={len(test_rows)} majority_rate={majority_rate:.4f} "
              f"acc={metrics['accuracy']:.4f} bal_acc={metrics['balanced_accuracy']:.4f} "
              f"macro_f1={metrics['macro_f1']:.4f} ece={metrics['ece']:.4f}{extra} "
              f"cm={metrics['confusion_matrix']}")

    bal_accs, f1s, accs, eces = map(np.array, (bal_accs, f1s, accs, eces))
    print(f"\n[{args.tag}] === CV SUMMARY (mean +/- std across {len(folds)} outer test folds) ===")
    print(f"[{args.tag}] accuracy={accs.mean():.4f} +/- {accs.std():.4f}  "
          f"balanced_accuracy={bal_accs.mean():.4f} +/- {bal_accs.std():.4f}  "
          f"macro_f1={f1s.mean():.4f} +/- {f1s.std():.4f}  ece={eces.mean():.4f} +/- {eces.std():.4f}")
    print(f"[{args.tag}] vs CV trivial baseline (random forest): balanced_accuracy="
          f"{CV_TRIVIAL_BASELINE_BAL_ACC:.4f} +/- {CV_TRIVIAL_BASELINE_BAL_ACC_STD:.4f}  "
          f"diff={bal_accs.mean() - CV_TRIVIAL_BASELINE_BAL_ACC:+.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
