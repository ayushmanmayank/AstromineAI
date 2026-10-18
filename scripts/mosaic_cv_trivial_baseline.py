"""
Global-mosaic dataset v2, Stage 0 step 2: recompute the trivial
baseline (logistic regression + random forest on real per-tile albedo +
lat/lon) under the new 5-fold region-block CV (ml/utils/mosaic_cv.py).

This is the new reference number for the whole v2 task: 0.5530 balanced
accuracy / 0.5374 macro-F1 (the fixed 222-tile test set's number from
final/mosaic-dataset) is quoted as a bar to beat throughout this task,
but the ACTUAL comparison baseline for every model trained in this
branch is the CV mean +/- std computed here, since this branch's
primary metric is 5-fold CV, not that single fixed test set (left
untouched, never reused for tuning).

Uses ALL 1,494 real, non-buffered tiles from
datasets/mosaic/manifests/tile_manifest.csv (the original 'train' +
'val' + 'test' rows combined -- CV re-splits them itself; rows with
split == 'buffered_out' are excluded, same tiles the original pipeline
already excluded for the same reason).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.utils.mosaic_cv import N_FOLDS, make_cv_folds  # noqa: E402

MANIFEST_PATH = "datasets/mosaic/manifests/tile_manifest.csv"
BLOCK_SIZE_DEG = 20.0
TILE_SIZE_DEG = 224 / 74.1778  # same real FC resolution as scripts/mosaic_tile.py
SEED = 42


def load_all_kept_tiles(manifest_csv: str) -> list[dict]:
    with open(manifest_csv, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh) if row["split"] != "buffered_out"]


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
    rows = load_all_kept_tiles(MANIFEST_PATH)
    print(f"Real kept tiles (train+val+test, pre-CV-re-split): {len(rows)}")

    X = tile_features(rows)
    y = np.array([int(r["label"]) for r in rows])
    lats = [float(r["center_lat"]) for r in rows]
    lons = [float(r["center_lon"]) for r in rows]

    folds = make_cv_folds(lats, lons, BLOCK_SIZE_DEG, TILE_SIZE_DEG, n_folds=N_FOLDS, seed=SEED)
    print(f"Real CV folds: {len(folds)}")

    results: dict[str, dict[str, list[float]]] = {
        "logistic regression": {"balanced_accuracy": [], "macro_f1": []},
        "random forest": {"balanced_accuracy": [], "macro_f1": []},
    }

    for fold in folds:
        # Trivial baseline has no real hyperparameters to tune, so the
        # inner val fold is folded into the training fit (standard
        # practice when there is nothing to tune) -- the outer test
        # fold is still touched only here, once, as this fold's test set.
        train_idx = list(fold.train_idx) + list(fold.val_idx)
        X_train, y_train = X[train_idx], y[train_idx]
        X_test, y_test = X[list(fold.test_idx)], y[list(fold.test_idx)]

        majority_class = np.bincount(y_test).argmax()
        majority_rate = (y_test == majority_class).mean()

        for name, model in [
            ("logistic regression", LogisticRegression(max_iter=1000, random_state=SEED)),
            ("random forest", RandomForestClassifier(n_estimators=200, random_state=SEED, n_jobs=-1)),
        ]:
            model.fit(X_train, y_train)
            pred = model.predict(X_test)
            bal_acc = balanced_accuracy_score(y_test, pred)
            macro_f1 = f1_score(y_test, pred, average="macro", zero_division=0)
            results[name]["balanced_accuracy"].append(bal_acc)
            results[name]["macro_f1"].append(macro_f1)
            print(f"  fold {fold.fold_index}: n_test={len(y_test)} majority_rate={majority_rate:.4f} "
                  f"{name}: bal_acc={bal_acc:.4f} macro_f1={macro_f1:.4f}")

    print("\n=== CV summary (mean +/- std across 5 outer test folds) ===")
    for name, metrics in results.items():
        bal = np.array(metrics["balanced_accuracy"])
        f1 = np.array(metrics["macro_f1"])
        print(f"{name}: balanced_accuracy={bal.mean():.4f} +/- {bal.std():.4f}  "
              f"macro_f1={f1.mean():.4f} +/- {f1.std():.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
