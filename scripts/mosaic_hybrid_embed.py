"""
Global-mosaic dataset v2, Stage 2(c): hybrid model -- random forest on
frozen, off-the-shelf ImageNet ResNet-50 embeddings (penultimate
pooled features), real albedo, and real lat/lon, under the same 5-fold
region-block CV as every other result in this task.

Deliberately uses an ImageNet-pretrained backbone with ZERO Vesta
fine-tuning (not final/mosaic-dataset's resnet50_classweighted.pt
checkpoint): that checkpoint was fit using final/mosaic-dataset's own,
different train/val/test split, which overlaps with this task's new CV
test folds -- reusing it here would leak real label information about
tiles that are this CV's test set in at least one fold into the
"frozen" feature extractor. An off-the-shelf, never-fine-tuned backbone
has seen zero Vesta labels at all, so there is no such leakage, at the
cost of not testing a Vesta-adapted feature space -- a real, stated
trade-off, not an oversight.

Embeddings are computed once for every real tile (not per fold, since
the backbone is frozen and identical across folds) and cached, then a
plain random forest is fit per fold on [embedding, albedo, lat,
sin/cos lon] from that fold's train+val tiles and evaluated on its real
test tiles, exactly like every other trivial-baseline-style check in
this task.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score
from torchvision.models import ResNet50_Weights, resnet50

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.utils.mosaic_cv import N_FOLDS, make_cv_folds  # noqa: E402

MANIFEST_PATH = "datasets/mosaic/manifests/tile_manifest.csv"
BLOCK_SIZE_DEG = 20.0
TILE_SIZE_DEG = 224 / 74.1778
SEED = 42


def load_all_kept_tiles(manifest_csv: str) -> list[dict]:
    with open(manifest_csv, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh) if row["split"] != "buffered_out"]


def main() -> int:
    rows = load_all_kept_tiles(MANIFEST_PATH)
    print(f"Real kept tiles: {len(rows)}")

    device = "cpu"
    backbone = resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)
    backbone.fc = nn.Identity()  # expose the real 2048-d pooled feature
    backbone.eval().to(device)

    print("Extracting real, frozen ImageNet ResNet-50 embeddings for every tile (no Vesta fine-tuning)...")
    embeddings = np.zeros((len(rows), 2048), dtype=np.float32)
    albedo = np.zeros(len(rows), dtype=np.float32)
    lats = np.zeros(len(rows), dtype=np.float64)
    lons = np.zeros(len(rows), dtype=np.float64)
    y = np.zeros(len(rows), dtype=np.int64)

    batch_imgs, batch_idx = [], []
    BATCH = 16

    def flush():
        if not batch_imgs:
            return
        with torch.no_grad():
            tensor = torch.from_numpy(np.stack(batch_imgs)).float()
            feats = backbone(tensor).numpy()
        for j, idx in enumerate(batch_idx):
            embeddings[idx] = feats[j]
        batch_imgs.clear()
        batch_idx.clear()

    for i, row in enumerate(rows):
        pil_image = Image.open(row["path"]).convert("L").resize((224, 224), Image.BILINEAR)
        arr = np.asarray(pil_image, dtype=np.float32) / 255.0
        albedo[i] = float(arr.mean() * 255.0)
        lats[i] = float(row["center_lat"])
        lons[i] = float(row["center_lon"])
        y[i] = int(row["label"])

        arr3 = np.stack([arr, arr, arr], axis=0)
        batch_imgs.append(arr3)
        batch_idx.append(i)
        if len(batch_imgs) == BATCH:
            flush()
        if (i + 1) % 200 == 0:
            print(f"  embedded {i + 1}/{len(rows)}")
    flush()
    print("Done extracting embeddings.")

    lon_rad = np.deg2rad(lons)
    X = np.column_stack([embeddings, albedo, lats, np.sin(lon_rad), np.cos(lon_rad)])

    folds = make_cv_folds(list(lats), list(lons), BLOCK_SIZE_DEG, TILE_SIZE_DEG, n_folds=N_FOLDS, seed=SEED)
    print(f"Real CV folds: {len(folds)}")

    bal_accs, f1s, accs = [], [], []
    for fold in folds:
        train_idx = list(fold.train_idx) + list(fold.val_idx)
        test_idx = list(fold.test_idx)
        model = RandomForestClassifier(n_estimators=300, random_state=SEED, n_jobs=-1)
        model.fit(X[train_idx], y[train_idx])
        pred = model.predict(X[test_idx])
        bal_acc = balanced_accuracy_score(y[test_idx], pred)
        f1 = f1_score(y[test_idx], pred, average="macro", zero_division=0)
        acc = (pred == y[test_idx]).mean()
        cm = confusion_matrix(y[test_idx], pred, labels=[0, 1, 2]).tolist()
        bal_accs.append(bal_acc)
        f1s.append(f1)
        accs.append(acc)
        print(f"fold {fold.fold_index}: n_test={len(test_idx)} acc={acc:.4f} bal_acc={bal_acc:.4f} macro_f1={f1:.4f} cm={cm}")

    bal_accs, f1s, accs = map(np.array, (bal_accs, f1s, accs))
    print(f"\n=== Stage 2(c) hybrid (frozen ImageNet ResNet-50 embeddings + albedo + lat/lon, random forest) CV SUMMARY ===")
    print(f"accuracy={accs.mean():.4f} +/- {accs.std():.4f}  balanced_accuracy={bal_accs.mean():.4f} +/- {bal_accs.std():.4f}  "
          f"macro_f1={f1s.mean():.4f} +/- {f1s.std():.4f}")
    print(f"vs CV trivial baseline (albedo+lat/lon only, random forest): balanced_accuracy=0.7783 +/- 0.0659  "
          f"diff={bal_accs.mean() - 0.7783:+.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
