"""
Global-mosaic dataset v2, Stage 4 (optional task variant): trivial
baseline (random forest on real per-tile albedo + lat/lon) for the
2-class task (ml/data/mosaic_labels_v2.py -- drops band1_mid, reuses
the already-committed tertile thresholds). Reported separately from the
3-class numbers throughout, per this stage's own rule.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.mosaic_labels_v2 import remap_tertile_to_2class  # noqa: E402
from ml.utils.mosaic_cv import N_FOLDS, make_cv_folds  # noqa: E402

MANIFEST_PATH = "datasets/mosaic/manifests/tile_manifest.csv"
BLOCK_SIZE_DEG = 20.0
TILE_SIZE_DEG = 224 / 74.1778
SEED = 42


def load_2class_tiles(manifest_csv: str) -> list[dict]:
    with open(manifest_csv, newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.DictReader(fh) if row["split"] != "buffered_out"]
    out = []
    for r in rows:
        new_label = remap_tertile_to_2class(int(r["label"]))
        if new_label == -1:
            continue
        r = dict(r)
        r["label"] = str(new_label)
        out.append(r)
    return out


def tile_features(rows: list[dict]) -> np.ndarray:
    feats = []
    for row in rows:
        img = np.asarray(Image.open(row["path"]).convert("L"), dtype=np.float32)
        albedo = float(img.mean())
        lat = float(row["center_lat"])
        lon_rad = np.deg2rad(float(row["center_lon"]))
        feats.append([albedo, lat, np.sin(lon_rad), np.cos(lon_rad)])
    return np.array(feats)


def main() -> int:
    rows = load_2class_tiles(MANIFEST_PATH)
    print(f"Real 2-class tiles (band1_mid dropped): {len(rows)}")

    X = tile_features(rows)
    y = np.array([int(r["label"]) for r in rows])
    lats = [float(r["center_lat"]) for r in rows]
    lons = [float(r["center_lon"]) for r in rows]

    folds = make_cv_folds(lats, lons, BLOCK_SIZE_DEG, TILE_SIZE_DEG, n_folds=N_FOLDS, seed=SEED)
    print(f"Real CV folds: {len(folds)}")

    bal_accs, f1s = [], []
    for fold in folds:
        train_idx = list(fold.train_idx) + list(fold.val_idx)
        test_idx = list(fold.test_idx)
        model = RandomForestClassifier(n_estimators=200, random_state=SEED, n_jobs=-1)
        model.fit(X[train_idx], y[train_idx])
        pred = model.predict(X[test_idx])
        majority_rate = np.bincount(y[test_idx]).max() / len(test_idx)
        bal_acc = balanced_accuracy_score(y[test_idx], pred)
        f1 = f1_score(y[test_idx], pred, average="macro", zero_division=0)
        bal_accs.append(bal_acc)
        f1s.append(f1)
        print(f"fold {fold.fold_index}: n_test={len(test_idx)} majority_rate={majority_rate:.4f} "
              f"bal_acc={bal_acc:.4f} macro_f1={f1:.4f}")

    bal_accs, f1s = np.array(bal_accs), np.array(f1s)
    print(f"\n=== 2-class trivial baseline (random forest) CV SUMMARY ===")
    print(f"balanced_accuracy={bal_accs.mean():.4f} +/- {bal_accs.std():.4f}  "
          f"macro_f1={f1s.mean():.4f} +/- {f1s.std():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
