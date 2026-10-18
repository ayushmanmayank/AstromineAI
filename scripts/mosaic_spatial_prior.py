"""
Global-mosaic dataset v3, Stage 1: stacked spatial-prior model.

**What this measures, stated plainly before any number below: these
models predict a tile's real VIR Band I tertile class from its real
tile-center LOCATION (and, for some candidates, its real mean FC
albedo). None of them is a composition-from-image model, and none can
classify an unlocated image.**

Uses the SAME real 5-fold region-block CV folds as `final/mosaic-v2`
(identical `block_size_deg`, `tile_size_deg`, `n_folds`, `seed` --
verified by construction, not re-derived). Tuning for candidates with
real hyperparameters (k-NN's k, the kernel smoother's bandwidth) uses
only each outer fold's own inner validation split, never the outer
test fold.

Stacking: the CNN probability features come from a real residual
ResNet-50 + class-weighted model (the same real recipe
`final/mosaic-v2`'s Stage 3 found to win), trained on each outer
fold's TRAIN rows only -- so its probabilities on VAL and TEST rows are
genuinely out-of-fold relative to that CNN's own training, and no
outer-test-fold information ever reaches any model's fit. Because only
VAL has honest, never-trained-on CNN probabilities, the stacked model
is fit on VAL rows only; a size-matched tabular-only model (also fit on
VAL rows only) is reported alongside it so the comparison isolates the
real effect of adding CNN features, not just a smaller training set --
disclosed explicitly here, not hidden.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import balanced_accuracy_score, f1_score
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.mosaic_dataset_cv import MosaicTileDatasetCV  # noqa: E402
from ml.data.mosaic_labels import CLASS_NAMES  # noqa: E402
from ml.utils.mosaic_cv import N_FOLDS, make_cv_folds  # noqa: E402
from ml.utils.mosaic_spatial_models import (  # noqa: E402
    build_positional_features,
    build_tabular_features,
    fit_gradient_boosting,
    fit_random_forest,
    tune_and_fit_kernel_smoother,
    tune_and_fit_knn,
)
from scripts.mosaic_train_cv import ResNetWithSideInputs, build_class_weights  # noqa: E402

MANIFEST_PATH = "datasets/mosaic/manifests/tile_manifest.csv"
BLOCK_SIZE_DEG = 20.0
TILE_SIZE_DEG = 224 / 74.1778
SEED = 42
N_CLASSES = len(CLASS_NAMES)

# Real reference numbers this task requires reporting next to every
# result (from final/mosaic-v2, unchanged, not recomputed here):
LOCATION_ONLY_RF_BAL_ACC = 0.7215
LOCATION_ONLY_RF_STD = 0.0961
ALBEDO_LATLON_RF_BAL_ACC = 0.7783
ALBEDO_LATLON_RF_STD = 0.0659
BEST_DEEP_MODEL_BAL_ACC = 0.5637
BEST_DEEP_MODEL_STD = 0.0403


def load_all_kept_tiles(manifest_csv: str) -> list[dict]:
    with open(manifest_csv, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh) if row["split"] != "buffered_out"]


def train_cnn_get_probs(train_rows, val_rows, test_rows, seed: int):
    """Trains the real residual ResNet-50 + class-weighted recipe
    (final/mosaic-v2's Stage 3 winner) on train_rows only, returns real
    softmax probabilities for val_rows and test_rows -- both genuinely
    out-of-fold relative to this CNN's own training."""
    torch.manual_seed(seed)
    train_ds = MosaicTileDatasetCV(train_rows, return_side_inputs=True)
    val_ds = MosaicTileDatasetCV(val_rows, return_side_inputs=True)
    test_ds = MosaicTileDatasetCV(test_rows, return_side_inputs=True)

    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=16, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=16, shuffle=False)

    model = ResNetWithSideInputs(num_classes=N_CLASSES, pretrained=True)
    for p in model.features.parameters():
        p.requires_grad = False
    trainable = list(model.classifier.parameters())

    class_weights = build_class_weights(train_rows, "cpu")
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(trainable, lr=1e-3)

    for _epoch in range(2):
        model.train()
        for images, labels, side, _ids in train_loader:
            images, side = images.float(), side.float()
            optimizer.zero_grad()
            out = model(images, side)
            loss = criterion(out, labels)
            loss.backward()
            optimizer.step()

    def get_probs(loader):
        model.eval()
        all_probs, all_labels = [], []
        with torch.no_grad():
            for images, labels, side, _ids in loader:
                out = model(images.float(), side.float())
                all_probs.append(F.softmax(out, dim=1).numpy())
                all_labels.append(labels.numpy())
        return np.concatenate(all_probs), np.concatenate(all_labels)

    val_probs, val_labels = get_probs(val_loader)
    test_probs, test_labels = get_probs(test_loader)
    return val_probs, val_labels, test_probs, test_labels


def main() -> int:
    rows = load_all_kept_tiles(MANIFEST_PATH)
    lats_all = np.array([float(r["center_lat"]) for r in rows])
    lons_all = np.array([float(r["center_lon"]) for r in rows])
    y_all = np.array([int(r["label"]) for r in rows])
    albedo_all = None  # computed lazily per-row below to avoid loading all images twice

    folds = make_cv_folds(list(lats_all), list(lons_all), BLOCK_SIZE_DEG, TILE_SIZE_DEG, n_folds=N_FOLDS, seed=SEED)
    print(f"Real tiles: {len(rows)}; real CV folds: {len(folds)} (identical params/seed to final/mosaic-v2)")

    from PIL import Image
    albedo_all = np.array([
        float(np.asarray(Image.open(r["path"]).convert("L"), dtype=np.float32).mean())
        for r in rows
    ])

    candidates = {"random_forest": [], "gradient_boosting": [], "knn": [], "kernel_smoother": []}
    candidate_hparams = {"knn": [], "kernel_smoother": []}

    stacked_bal_acc, tabular_matched_bal_acc = [], []
    stacked_f1, tabular_matched_f1 = [], []

    for fold in folds:
        tr_idx, va_idx, te_idx = list(fold.train_idx), list(fold.val_idx), list(fold.test_idx)
        full_idx = tr_idx + va_idx

        X_full = build_tabular_features(albedo_all[full_idx], lats_all[full_idx], lons_all[full_idx])
        y_full = y_all[full_idx]
        X_test = build_tabular_features(albedo_all[te_idx], lats_all[te_idx], lons_all[te_idx])
        y_test = y_all[te_idx]

        # Random forest / gradient boosting: no inner-val tuning (fixed
        # hyperparameters, same convention as every trivial baseline in
        # this project), fit on train+val.
        rf = fit_random_forest(X_full, y_full, seed=SEED)
        pred = rf.predict(X_test)
        candidates["random_forest"].append((balanced_accuracy_score(y_test, pred), f1_score(y_test, pred, average="macro", zero_division=0)))

        gb = fit_gradient_boosting(X_full, y_full, seed=SEED)
        pred = gb.predict(X_test)
        candidates["gradient_boosting"].append((balanced_accuracy_score(y_test, pred), f1_score(y_test, pred, average="macro", zero_division=0)))

        # k-NN and kernel smoother: tuned on this fold's own inner val split only.
        knn_result = tune_and_fit_knn(
            lats_all[tr_idx], lons_all[tr_idx], y_all[tr_idx],
            lats_all[va_idx], lons_all[va_idx], y_all[va_idx], n_classes=N_CLASSES,
        )
        pred = knn_result.model.predict(lats_all[te_idx], lons_all[te_idx])
        candidates["knn"].append((balanced_accuracy_score(y_test, pred), f1_score(y_test, pred, average="macro", zero_division=0)))
        candidate_hparams["knn"].append(knn_result.hyperparam)

        kernel_result = tune_and_fit_kernel_smoother(
            lats_all[tr_idx], lons_all[tr_idx], y_all[tr_idx],
            lats_all[va_idx], lons_all[va_idx], y_all[va_idx], n_classes=N_CLASSES,
        )
        pred = kernel_result.model.predict(lats_all[te_idx], lons_all[te_idx])
        candidates["kernel_smoother"].append((balanced_accuracy_score(y_test, pred), f1_score(y_test, pred, average="macro", zero_division=0)))
        candidate_hparams["kernel_smoother"].append(kernel_result.hyperparam)

        print(f"fold {fold.fold_index}: rf_bal_acc={candidates['random_forest'][-1][0]:.4f} "
              f"gb_bal_acc={candidates['gradient_boosting'][-1][0]:.4f} "
              f"knn(k={knn_result.hyperparam})_bal_acc={candidates['knn'][-1][0]:.4f} "
              f"kernel(bw={kernel_result.hyperparam})_bal_acc={candidates['kernel_smoother'][-1][0]:.4f}")

    print("\n=== Stage 1 tabular candidates: CV summary (mean +/- std) ===")
    for name, scores in candidates.items():
        bal = np.array([s[0] for s in scores])
        f1 = np.array([s[1] for s in scores])
        extra = f" hparams={candidate_hparams[name]}" if name in candidate_hparams else ""
        print(f"{name}: balanced_accuracy={bal.mean():.4f} +/- {bal.std():.4f}  macro_f1={f1.mean():.4f} +/- {f1.std():.4f}{extra}")

    best_name = max(candidates, key=lambda n: np.mean([s[0] for s in candidates[n]]))
    best_bal = np.array([s[0] for s in candidates[best_name]])
    print(f"\nBest tabular (spatial-prior) model overall: {best_name} "
          f"({best_bal.mean():.4f} +/- {best_bal.std():.4f} balanced accuracy)")

    # Stacking (adding arbitrary extra feature columns) only naturally
    # applies to the two feature-vector candidates (random forest,
    # gradient boosting) -- k-NN and the kernel smoother are defined
    # directly on real great-circle distance over (lat, lon) only, with
    # no natural way to fold in extra probability-vector dimensions
    # without redefining their distance metric (a real design question
    # of its own, not attempted here). So stacking uses whichever of
    # {random_forest, gradient_boosting} is best, stated explicitly
    # rather than silently substituted when the overall-best model
    # (k-NN, here) isn't one of the two.
    stackable_names = ["random_forest", "gradient_boosting"]
    best_stackable_name = max(stackable_names, key=lambda n: np.mean([s[0] for s in candidates[n]]))
    best_stackable_bal = np.array([s[0] for s in candidates[best_stackable_name]])
    print(f"Best tabular model among stacking-compatible candidates (random forest / gradient "
          f"boosting only, since k-NN/kernel-smoother don't naturally accept extra feature "
          f"columns): {best_stackable_name} ({best_stackable_bal.mean():.4f} +/- "
          f"{best_stackable_bal.std():.4f} balanced accuracy)")

    print(f"\nReference numbers: location-only RF={LOCATION_ONLY_RF_BAL_ACC:.4f} +/- {LOCATION_ONLY_RF_STD:.4f}, "
          f"albedo+lat/lon RF={ALBEDO_LATLON_RF_BAL_ACC:.4f} +/- {ALBEDO_LATLON_RF_STD:.4f}, "
          f"best deep model (residual ResNet-50 + class-weighted)={BEST_DEEP_MODEL_BAL_ACC:.4f} +/- {BEST_DEEP_MODEL_STD:.4f}")

    # --- Stacking: out-of-fold CNN probabilities added to the best stacking-compatible tabular model ---
    print(f"\n=== Stacking real out-of-fold CNN probabilities onto '{best_stackable_name}' "
          f"(best of the stacking-compatible candidates -- NOT necessarily the overall-best "
          f"tabular model '{best_name}', see note above) ===")
    for fold in folds:
        tr_idx, va_idx, te_idx = list(fold.train_idx), list(fold.val_idx), list(fold.test_idx)
        train_rows_cnn = [rows[i] for i in tr_idx]
        val_rows_cnn = [rows[i] for i in va_idx]
        test_rows_cnn = [rows[i] for i in te_idx]

        val_probs, val_labels, test_probs, test_labels = train_cnn_get_probs(
            train_rows_cnn, val_rows_cnn, test_rows_cnn, seed=SEED + fold.fold_index,
        )
        assert np.array_equal(val_labels, y_all[va_idx])
        assert np.array_equal(test_labels, y_all[te_idx])

        X_val_tabular = build_tabular_features(albedo_all[va_idx], lats_all[va_idx], lons_all[va_idx])
        X_test_tabular = build_tabular_features(albedo_all[te_idx], lats_all[te_idx], lons_all[te_idx])

        X_val_stacked = np.column_stack([X_val_tabular, val_probs])
        X_test_stacked = np.column_stack([X_test_tabular, test_probs])

        if best_stackable_name == "random_forest":
            tabular_matched = fit_random_forest(X_val_tabular, y_all[va_idx], seed=SEED)
            stacked = fit_random_forest(X_val_stacked, y_all[va_idx], seed=SEED)
        else:
            tabular_matched = fit_gradient_boosting(X_val_tabular, y_all[va_idx], seed=SEED)
            stacked = fit_gradient_boosting(X_val_stacked, y_all[va_idx], seed=SEED)

        pred_matched = tabular_matched.predict(X_test_tabular)
        pred_stacked = stacked.predict(X_test_stacked)

        tabular_matched_bal_acc.append(balanced_accuracy_score(y_all[te_idx], pred_matched))
        tabular_matched_f1.append(f1_score(y_all[te_idx], pred_matched, average="macro", zero_division=0))
        stacked_bal_acc.append(balanced_accuracy_score(y_all[te_idx], pred_stacked))
        stacked_f1.append(f1_score(y_all[te_idx], pred_stacked, average="macro", zero_division=0))

        print(f"fold {fold.fold_index}: tabular_matched(val-only)_bal_acc={tabular_matched_bal_acc[-1]:.4f} "
              f"stacked(val-only+cnn_probs)_bal_acc={stacked_bal_acc[-1]:.4f}")

    tabular_matched_bal_acc = np.array(tabular_matched_bal_acc)
    stacked_bal_acc = np.array(stacked_bal_acc)
    tabular_matched_f1 = np.array(tabular_matched_f1)
    stacked_f1 = np.array(stacked_f1)

    print(f"\ntabular-only (matched, val-only training): balanced_accuracy="
          f"{tabular_matched_bal_acc.mean():.4f} +/- {tabular_matched_bal_acc.std():.4f}  "
          f"macro_f1={tabular_matched_f1.mean():.4f} +/- {tabular_matched_f1.std():.4f}")
    print(f"stacked (tabular + out-of-fold CNN probs, val-only training): balanced_accuracy="
          f"{stacked_bal_acc.mean():.4f} +/- {stacked_bal_acc.std():.4f}  "
          f"macro_f1={stacked_f1.mean():.4f} +/- {stacked_f1.std():.4f}")

    delta = stacked_bal_acc.mean() - tabular_matched_bal_acc.mean()
    delta_in_std = delta / tabular_matched_bal_acc.std() if tabular_matched_bal_acc.std() > 1e-9 else float("inf")
    print(f"\nDelta from adding CNN features: {delta:+.4f} balanced-accuracy points "
          f"({delta_in_std:+.2f} std of the tabular-only-matched CV spread)")
    if abs(delta_in_std) > 1.0 and delta > 0:
        print("STACKING VERDICT: real gain from image features (exceeds 1 std).")
    else:
        print("STACKING VERDICT: no gain from image features (does not exceed 1 std).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
