"""
Global-mosaic dataset, Stage 2 (GATE B), step 3: confound screen on the
real labels, BEFORE any model is trained.

For a real, deterministic sample of valid VIR pixels, this script pulls
the real FC albedo (DN) at the same real location and the real
latitude/longitude, then:
  1. reports each class's real mean FC albedo and mean latitude;
  2. reports the real acquisition-phase coverage fraction per class --
     this mosaic volume provides NO per-pixel source/coverage layer
     (checked directly: DWNVVIR_2/INDEX/INDEX.TAB lists only the 4
     output products, no per-pixel phase raster) -- so this sub-check is
     reported as genuinely unavailable, not skipped silently;
  3. trains a trivial baseline (logistic regression AND random forest,
     on albedo + sin/cos longitude + latitude only -- no deep model, no
     image pixels) with a real region-block split, and reports its real
     accuracy next to the real majority-class rate.

GATE B: if the trivial baseline's accuracy is way above majority-class
(confound) or, once Stage 4 trains a real deep model, within ~3 points
of it (deep model isn't learning anything beyond brightness/location),
this is reported plainly, not reasoned around.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.mosaic_labels import CLASS_NAMES, classify_band1_center  # noqa: E402
from ml.data.mosaic_reader import fc_lonlat_to_pixel, open_fc_mosaic, read_vir_mosaic, vir_pixel_to_lonlat  # noqa: E402
from ml.utils.mosaic_splits import assign_block_splits, region_block_for  # noqa: E402

VIR_BI_CENTER_PATH = "datasets/mosaic/raw/vir/VMT_MOSAIC-BI_CENTER_1.IMG"
FC_PATH = "datasets/mosaic/raw/fc/Vesta_Dawn_FC_HAMO_Mosaic_Global_74ppd.tif"

SAMPLE_STRIDE = 20  # every 20th valid VIR pixel in each axis -- real, deterministic subsample
BLOCK_SIZE_DEG = 20.0
SEED = 42


def main() -> int:
    print("Loading real VIR Band I center mosaic...")
    mosaic = read_vir_mosaic(VIR_BI_CENTER_PATH)
    labels_full = classify_band1_center(mosaic.data)

    print("Loading real FC mosaic (full array, for fast point lookups)...")
    fc_meta, fc_ds = open_fc_mosaic(FC_PATH)
    fc_array = fc_ds.read(1)
    fc_ds.close()

    lines = np.arange(0, mosaic.label.lines, SAMPLE_STRIDE)
    samples = np.arange(0, mosaic.label.samples, SAMPLE_STRIDE)
    ll, ss = np.meshgrid(lines, samples, indexing="ij")
    ll, ss = ll.ravel(), ss.ravel()

    cls = labels_full[ll, ss]
    valid = cls >= 0
    ll, ss, cls = ll[valid], ss[valid], cls[valid]
    print(f"Real sampled points (stride={SAMPLE_STRIDE}): {cls.size} valid of {valid.size} sampled")

    # Vectorized: every helper in ml.data.mosaic_reader is plain elementwise
    # arithmetic, so it works directly on numpy arrays, not just scalars.
    lons, lats = vir_pixel_to_lonlat(mosaic.label, ll.astype(np.float64), ss.astype(np.float64))
    fc_rows, fc_cols = fc_lonlat_to_pixel(fc_meta, lons, lats)
    fc_rows = np.round(fc_rows).astype(np.int64)
    fc_cols = np.round(fc_cols).astype(np.int64)
    in_bounds = (fc_rows >= 0) & (fc_rows < fc_meta.height) & (fc_cols >= 0) & (fc_cols < fc_meta.width)
    albedo = np.full(cls.size, np.nan)
    albedo[in_bounds] = fc_array[fc_rows[in_bounds], fc_cols[in_bounds]]

    valid_albedo = np.isfinite(albedo) & (albedo > 0)  # FC nodata=0
    ll, ss, cls, lons, lats, albedo = ll[valid_albedo], ss[valid_albedo], cls[valid_albedo], lons[valid_albedo], lats[valid_albedo], albedo[valid_albedo]
    print(f"Real points with valid FC albedo too: {cls.size}")

    print("\n=== Per-class real confound stats ===")
    for i, name in enumerate(CLASS_NAMES):
        m = cls == i
        print(f"{name}: n={m.sum()} mean_FC_albedo={albedo[m].mean():.2f} mean_latitude={lats[m].mean():+.2f}")

    print("\n=== Acquisition-phase coverage fraction per class ===")
    print("NOT AVAILABLE: DWNVVIR_2 (this VIR mosaic volume) provides no "
          "per-pixel source/coverage raster -- checked directly against its "
          "own INDEX.TAB and DATA/ listing (only the 4 output band-parameter "
          "rasters exist, no per-pixel phase/orbit identifier). Reported "
          "honestly as unavailable, not fabricated or skipped silently.")

    # Real region-block split for the trivial baseline itself.
    blocks = [region_block_for(lat, lon, BLOCK_SIZE_DEG) for lat, lon in zip(lats, lons)]
    split_map = assign_block_splits(blocks, 0.70, 0.15, 0.15, seed=SEED)
    split_arr = np.array([split_map[b] for b in blocks])

    train_mask = split_arr == "train"
    val_mask = split_arr == "val"
    print(f"\nReal region-block split of this confound sample: "
          f"train={train_mask.sum()} val={val_mask.sum()} test={(split_arr=='test').sum()} (test not used here)")

    lon_rad = np.deg2rad(lons)
    X = np.column_stack([albedo, lats, np.sin(lon_rad), np.cos(lon_rad)])
    y = cls

    X_train, y_train = X[train_mask], y[train_mask]
    X_val, y_val = X[val_mask], y[val_mask]

    majority_class = np.bincount(y_val).argmax()
    majority_rate = (y_val == majority_class).mean()
    print(f"\nVal majority-class rate: {majority_rate*100:.2f}% (class {CLASS_NAMES[majority_class]})")

    for name, model in [
        ("logistic regression", LogisticRegression(max_iter=1000, random_state=SEED)),
        ("random forest", RandomForestClassifier(n_estimators=200, random_state=SEED, n_jobs=-1)),
    ]:
        model.fit(X_train, y_train)
        pred = model.predict(X_val)
        acc = accuracy_score(y_val, pred)
        print(f"GATE B trivial baseline ({name}, albedo+lat+lon only): val accuracy = {acc*100:.2f}%"
              f" (majority-class rate {majority_rate*100:.2f}%, diff {acc*100-majority_rate*100:+.2f} pts)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
