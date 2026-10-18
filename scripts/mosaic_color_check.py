"""
Global-mosaic dataset v2, Stage 1 (Gate C): does the real Dawn FC2
color-filter data add signal beyond the trivial baseline?

Real source, recorded with sha256/size in
datasets/mosaic/manifests/color_acquisition_manifest.json (separate
new manifest -- final/mosaic-dataset's own acquisition_manifest.json is
left untouched): sbnarchive.psi.edu, volume DWNVFC2_2
(`DAWN-A-FC2-5-MOSAIC-V1.0`, "Dawn FC2 High Level (2/3) Vesta Encounter
Mosaics"), DATA/HAMO_COLOR/, real cylindrical global mosaics for
filters F3 (749nm), F4 (917nm), F5 (965nm) -- read directly from each
file's own CENTER_FILTER_WAVELENGTH field, not assumed from a generic
filter table (an initial assumption based on a remembered table was
WRONG -- see ml/data/mosaic_color_reader.py's docstring -- and was
caught by a byte-range probe of every real file's own label before any
full download relied on it). These three bands match this task's named
"750/920 nm, 965/750 nm" ratio recipe: 750nm->F3, 920nm->F4,
965nm->F5, so ratio1 = F3/F4 (~750/920) and ratio2 = F5/F3 (~965/750).

Real empirical longitude-convention check (printed below, same
discipline as the original Rheasilvia check in
scripts/mosaic_crater_check.py, but using structural cross-correlation
against the already-trusted FC clear-filter mosaic instead of a
spectral-composition argument, since this is a broadband albedo image,
not a derived spectral quantity): lon_sign=+1, lon_offset_deg=-150.0 --
note the SIGN IS OPPOSITE VIR's (-1), confirmed, not assumed, to carry
over; the PDS3 SIS leaves this implementation-defined per-dataset
(ml/data/mosaic_reader.py's own documented finding), and FC2's color
mosaics are produced by a different pipeline than VIR's, so this was
re-tested from scratch rather than reused.

GATE C: if color-ratio features (+ albedo + lat/lon) do not beat the
pure albedo+lat/lon trivial baseline (ml/utils/mosaic_cv.py CV, random
forest) by more than 1 std of the CV spread, report "no extra signal in
available FC color data" and continue to Stage 2 on the existing
single-band data only.
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

from ml.data.mosaic_color_reader import read_center_filter_wavelength_nm, read_pds3_scalar_mosaic  # noqa: E402
from ml.data.mosaic_reader import fc_lonlat_to_pixel, open_fc_mosaic, fc_pixel_to_lonlat  # noqa: E402
from ml.utils.mosaic_cv import N_FOLDS, make_cv_folds  # noqa: E402

MANIFEST_PATH = "datasets/mosaic/manifests/tile_manifest.csv"
FC_PATH = "datasets/mosaic/raw/fc/Vesta_Dawn_FC_HAMO_Mosaic_Global_74ppd.tif"
COLOR_DIR = Path("datasets/mosaic/raw/fc_color")
COLOR_FILES = {
    "F3": COLOR_DIR / "VE_HAMO_00N_330E_CYL_FILT3.IMG",
    "F4": COLOR_DIR / "VE_HAMO_00N_330E_CYL_FILT4.IMG",
    "F5": COLOR_DIR / "VE_HAMO_00N_330E_CYL_FILT5.IMG",
}

# Empirically confirmed above (structural cross-correlation against the
# real, already-trusted FC clear-filter mosaic at Rheasilvia, Divalia
# Fossae, Marcia; search +/-25px for the best local alignment, correcting
# for the small 74.1765 vs 74.1778 px/deg resolution mismatch between this
# color volume and the primary 74ppd FC GeoTIFF):
#   lon_sign=+1: Rheasilvia corr=+0.4031, Divalia_Fossae corr=+0.6226,
#                Marcia corr=+0.2419
#   lon_sign=-1: Rheasilvia corr=+0.2281, Divalia_Fossae corr=+0.1380,
#                Marcia corr=+0.2336
#   lon_offset=-150.0 beats lon_offset=0.0 at all 3 points under sign=+1
#     (Rheasilvia +0.4031 vs +0.0466; Divalia_Fossae +0.6226 vs +0.3176;
#      Marcia +0.2419 vs +0.2194).
_COLOR_LON_SIGN = 1
_COLOR_LON_OFFSET_DEG = -150.0

BLOCK_SIZE_DEG = 20.0
TILE_SIZE_DEG = 224 / 74.1778
SEED = 42

# Real, additional cleaning step specific to these FC2 color rasters
# (undocumented in the label -- MISSING_CONSTANT=-1e32 is declared and
# handled generically in ml/data/mosaic_color_reader.py, but a tiny,
# separate population of undeclared, non-physical outlier values
# (~1e29 scale, far outside any plausible photometric reflectance
# range) was found empirically in the real F5 raster: ~55,221 of
# 356,511,753 pixels (0.0155%) -- not caught by the generic reader's
# sentinel handling since they are neither close to -1e32 nor above the
# reader's own 1e30 cutoff. Reflectance physically cannot exceed a few
# units for an airless body, so anything outside this generous range is
# treated as an additional, explicitly-documented artifact here, not in
# the generic reader (which stays faithful only to the label's own
# declared sentinel).
_PLAUSIBLE_REFLECTANCE_RANGE = (0.0, 5.0)


def color_lonlat_to_pixel(label, claudia_lon_deg: float, lat_deg: float) -> tuple[float, float]:
    label_lon_deg = (claudia_lon_deg + _COLOR_LON_OFFSET_DEG) % 360.0
    sample = (
        label.sample_projection_offset_px + 1
        + _COLOR_LON_SIGN * (label_lon_deg - label.center_longitude_deg) * label.map_resolution_px_per_deg
    )
    line = label.line_projection_offset_px + 1 - (lat_deg - label.center_latitude_deg) * label.map_resolution_px_per_deg
    return line, sample


def clean_reflectance(arr: np.ndarray) -> np.ndarray:
    lo, hi = _PLAUSIBLE_REFLECTANCE_RANGE
    out = np.where((arr >= lo) & (arr <= hi), arr, np.nan)
    return out


def load_all_kept_tiles(manifest_csv: str) -> list[dict]:
    with open(manifest_csv, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh) if row["split"] != "buffered_out"]


def main() -> int:
    print("Real FC2 color-filter wavelengths (read from each file's own label):")
    for name, path in COLOR_FILES.items():
        wave = read_center_filter_wavelength_nm(path)
        print(f"  {name} ({path.name}): {wave:.0f} nm")

    print("\nConfirmed longitude convention for this color volume (structural "
          f"cross-correlation vs. trusted FC mosaic): lon_sign={_COLOR_LON_SIGN:+d}, "
          f"lon_offset_deg={_COLOR_LON_OFFSET_DEG} (opposite sign from VIR's -1 -- "
          "re-verified empirically, not assumed to carry over; see module docstring).")

    print("\nLoading real color-filter mosaics (F3, F4, F5)...")
    color_mosaics = {name: read_pds3_scalar_mosaic(path) for name, path in COLOR_FILES.items()}
    for name, m in color_mosaics.items():
        cleaned = clean_reflectance(m.data)
        n_valid = np.isfinite(cleaned).sum()
        print(f"  {name}: {n_valid} valid of {cleaned.size} pixels "
              f"({100*n_valid/cleaned.size:.2f}%), mean={np.nanmean(cleaned):.4f}")
        m.data = cleaned  # keep the cleaned array for downstream use

    print("\nLoading real tile manifest + FC mosaic for per-tile feature extraction...")
    rows = load_all_kept_tiles(MANIFEST_PATH)
    fc_meta, fc_ds = open_fc_mosaic(FC_PATH)
    fc_array = fc_ds.read(1)
    fc_ds.close()

    lats = np.array([float(r["center_lat"]) for r in rows])
    lons = np.array([float(r["center_lon"]) for r in rows])
    y = np.array([int(r["label"]) for r in rows])

    albedo = np.array([np.asarray(Image.open(r["path"]).convert("L"), dtype=np.float32).mean() for r in rows])

    HALF_WINDOW_PX = 5  # a small, real local window (not a single pixel) around each tile center, mean-pooled
    n_tiles = len(rows)
    color_means = {name: np.full(n_tiles, np.nan) for name in COLOR_FILES}
    n_coverage_missing = 0
    for i in range(n_tiles):
        any_missing = False
        for name, m in color_mosaics.items():
            line, sample = color_lonlat_to_pixel(m.label, lons[i], lats[i])
            l0, l1 = int(round(line)) - HALF_WINDOW_PX, int(round(line)) + HALF_WINDOW_PX + 1
            s0, s1 = int(round(sample)) - HALF_WINDOW_PX, int(round(sample)) + HALF_WINDOW_PX + 1
            if l0 < 0 or s0 < 0 or l1 > m.data.shape[0] or s1 > m.data.shape[1]:
                any_missing = True
                continue
            window = m.data[l0:l1, s0:s1]
            if np.isfinite(window).sum() == 0:
                any_missing = True
                continue
            color_means[name][i] = float(np.nanmean(window))
        if any_missing:
            n_coverage_missing += 1

    print(f"\nReal tiles with full F3+F4+F5 color coverage: {n_tiles - n_coverage_missing} of {n_tiles} "
          f"({n_coverage_missing} missing at least one band -- color imaging coverage is real and incomplete, "
          "see module docstring / AAREADME.TXT: HAMO-1 southern + HAMO-2 cycle-6 northern only, poor at high latitudes).")

    ratio1 = color_means["F3"] / color_means["F4"]  # ~750/920 nm
    ratio2 = color_means["F5"] / color_means["F3"]  # ~965/750 nm

    have_color = np.isfinite(ratio1) & np.isfinite(ratio2)
    print(f"Real tiles usable for the color-ratio hypothesis test: {have_color.sum()} of {n_tiles}")

    if have_color.sum() < 100:
        print("\nGATE C: FEWER THAN 100 real tiles have usable color-ratio coverage -- "
              "too little real data to run a meaningful hypothesis test. "
              "Reporting 'no extra signal testable from available FC color data' and continuing "
              "to Stage 2 on the existing single-band data only.")
        return 0

    lon_rad = np.deg2rad(lons)
    sin_lon, cos_lon = np.sin(lon_rad), np.cos(lon_rad)

    X_full = np.column_stack([albedo, lats, sin_lon, cos_lon])
    X_color = np.column_stack([albedo, lats, sin_lon, cos_lon, ratio1, ratio2])

    lats_c, lons_c = lats[have_color], lons[have_color]
    y_c = y[have_color]
    X_full_c = X_full[have_color]
    X_color_c = X_color[have_color]

    folds = make_cv_folds(list(lats_c), list(lons_c), BLOCK_SIZE_DEG, TILE_SIZE_DEG, n_folds=N_FOLDS, seed=SEED)
    print(f"\nReal CV folds over the color-coverage subset: {len(folds)}")

    def run_cv(X, y_arr, folds):
        bal_accs, f1s = [], []
        for fold in folds:
            train_idx = list(fold.train_idx) + list(fold.val_idx)
            test_idx = list(fold.test_idx)
            if len(test_idx) == 0 or len(train_idx) == 0:
                continue
            model = RandomForestClassifier(n_estimators=200, random_state=SEED, n_jobs=-1)
            model.fit(X[train_idx], y_arr[train_idx])
            pred = model.predict(X[test_idx])
            bal_accs.append(balanced_accuracy_score(y_arr[test_idx], pred))
            f1s.append(f1_score(y_arr[test_idx], pred, average="macro", zero_division=0))
        return np.array(bal_accs), np.array(f1s)

    bal_full, f1_full = run_cv(X_full_c, y_c, folds)
    bal_color, f1_color = run_cv(X_color_c, y_c, folds)

    print("\n=== Gate C: albedo+lat/lon vs. albedo+lat/lon+color-ratios, same CV subset ===")
    print(f"albedo+lat/lon only:            balanced_accuracy={bal_full.mean():.4f} +/- {bal_full.std():.4f}  "
          f"macro_f1={f1_full.mean():.4f} +/- {f1_full.std():.4f}")
    print(f"albedo+lat/lon+color-ratios:    balanced_accuracy={bal_color.mean():.4f} +/- {bal_color.std():.4f}  "
          f"macro_f1={f1_color.mean():.4f} +/- {f1_color.std():.4f}")

    gain = bal_color.mean() - bal_full.mean()
    std_spread = bal_full.std()
    print(f"\nGain from adding color-ratio features: {gain:+.4f} balanced-accuracy points "
          f"(1 std of the albedo+lat/lon CV spread = {std_spread:.4f})")

    if gain > std_spread:
        print("GATE C: color-ratio features BEAT the albedo+lat/lon baseline by more than 1 std "
              "of the CV spread -- real extra signal found in available FC color data.")
    else:
        print("GATE C: color-ratio features do NOT beat the albedo+lat/lon baseline by more than 1 std "
              "of the CV spread -- reporting 'no extra signal in available FC color data' and "
              "continuing to Stage 2 on the existing single-band data only.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
