"""
Global-mosaic dataset, Stage 1 (GATE A), step 3: empirically verify the
FC-vs-VIR longitude relationship by locating the same real features in
both mosaics, rather than trusting either label's documentation alone.

Real reference coordinates (IAU/USGS planetary gazetteer, same
convention this project's own Slice 11 investigation already used for
Rheasilvia -- see docs/month1_log.md):
  Rheasilvia (south polar impact basin): 71.950 S, 86.300 E
  Divalia Fossae (equatorial graben system): 9.050 S, 196.233 E

FC's own longitude scale needs no sign resolution (its embedded CRS's
central_meridian=0 is already the real, documented Claudia-Double-Prime-
aligned meridian -- see ml/data/mosaic_reader.py). VIR's label longitude
scale has a real, PDS3-standard sign ambiguity for
POSITIVE_LONGITUDE_DIRECTION=EAST equirectangular data (the SIS leaves
the sample-vs-longitude sign implementation-defined), on top of the
documented +150 degree offset to the Claudia-Double-Prime frame.

RESULT (this is the actual finding this script produced, not an
assumption -- including a real mistake caught and corrected along the
way): both candidate signs were tested quantitatively against
Rheasilvia's real, literature-documented compositional signature
(De Sanctis et al. 2012: diogenite -- shorter Band I wavelength --
concentrated within and around Rheasilvia; same citation this project's
own Slice 11 already used). An initial version of this test checked both
signs WITHOUT the real, documented +(-150 deg) Claudia-offset applied
first, got lon_sign=+1 as the apparent match, and very nearly locked that
in; re-running with the offset correctly applied first (since the sign
and the offset are not independent -- a 150 degree shift moves the
sampled pixel by nearly half the image width) flipped the result.
With the offset applied: lon_sign=-1 recovers a local Band I center mean
0.56 std BELOW the real global mean (shorter wavelength, exactly as the
literature predicts); lon_sign=+1 shows no such deviation (+0.21 std --
indistinguishable from background). **lon_sign=-1 is confirmed correct**
and is what ml.data.mosaic_reader.vir_lonlat_to_pixel() now implements
as the only option (not left as a runtime parameter).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.mosaic_reader import (  # noqa: E402
    _VIR_LABEL_LON_OFFSET_DEG,
    fc_lonlat_to_pixel,
    open_fc_mosaic,
    read_vir_mosaic,
    vir_lonlat_to_pixel,
)

FC_PATH = "datasets/mosaic/raw/fc/Vesta_Dawn_FC_HAMO_Mosaic_Global_74ppd.tif"
VIR_BI_CENTER_PATH = "datasets/mosaic/raw/vir/VMT_MOSAIC-BI_CENTER_1.IMG"
OUT_DIR = Path("datasets/mosaic/checks")
OUT_DIR.mkdir(parents=True, exist_ok=True)

REFERENCE_POINTS = [
    ("Rheasilvia", 86.300, -71.950),
    ("Divalia_Fossae", 196.233, -9.050),
]

FC_WINDOW_PX = 300   # ~4 deg at 74.18 px/deg
VIR_WINDOW_PX = 90   # ~2 deg at 44.5 px/deg
VIR_DISTRIBUTION_WINDOW_PX = 300  # ~6.7 deg -- large enough to span Rheasilvia's ~500 km extent


def _raw_vir_pixel(label, claudia_lon, lat, lon_sign):
    """Local re-implementation of the raw, sign-parameterized formula --
    kept here (not in ml/data/mosaic_reader.py) purely to document and
    reproduce the sign-determination evidence; production code only ever
    uses the one confirmed sign, via vir_lonlat_to_pixel()."""
    label_lon = (claudia_lon + _VIR_LABEL_LON_OFFSET_DEG) % 360.0
    sample = label.sample_projection_offset_px + 1 + lon_sign * (label_lon - label.center_longitude_deg) * label.map_resolution_px_per_deg
    line = label.line_projection_offset_px + 1 - (lat - label.center_latitude_deg) * label.map_resolution_px_per_deg
    return line, sample


def normalize_for_display(arr: np.ndarray) -> np.ndarray:
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return np.zeros_like(arr, dtype=np.uint8)
    lo, hi = np.nanpercentile(valid, [1, 99])
    if hi <= lo:
        hi = lo + 1e-6
    scaled = np.clip((arr - lo) / (hi - lo), 0, 1)
    scaled = np.nan_to_num(scaled, nan=0.0)
    return (scaled * 255).astype(np.uint8)


def sign_determination_check(mosaic) -> None:
    """The decisive evidence: compare each candidate sign's local Band I
    center mean at Rheasilvia against the real global distribution."""
    valid = mosaic.data[np.isfinite(mosaic.data)]
    global_mean, global_std = float(valid.mean()), float(valid.std())
    print(f"GLOBAL Band I center: n={valid.size} mean={global_mean:.5f} std={global_std:.5f}")

    for lon_sign in (1, -1):
        line, sample = _raw_vir_pixel(mosaic.label, 86.300, -71.950, lon_sign)
        line, sample = int(round(line)), int(round(sample))
        l0, l1 = max(0, line - VIR_DISTRIBUTION_WINDOW_PX), min(mosaic.label.lines, line + VIR_DISTRIBUTION_WINDOW_PX)
        s0, s1 = max(0, sample - VIR_DISTRIBUTION_WINDOW_PX), min(mosaic.label.samples, sample + VIR_DISTRIBUTION_WINDOW_PX)
        crop = mosaic.data[l0:l1, s0:s1]
        cv = crop[np.isfinite(crop)]
        local_mean = float(cv.mean())
        std_units = (local_mean - global_mean) / global_std
        verdict = "MATCHES diogenite signature (shorter wavelength)" if std_units < -0.3 else "no significant deviation"
        print(f"  lon_sign={lon_sign:+d}: local n={cv.size} mean={local_mean:.5f} "
              f"diff={local_mean - global_mean:+.5f} ({std_units:+.3f} std) -- {verdict}")


def crop_fc(ds, meta, lon, lat, half_px=FC_WINDOW_PX) -> np.ndarray:
    row, col = fc_lonlat_to_pixel(meta, lon, lat)
    row, col = int(round(row)), int(round(col))
    r0, r1 = max(0, row - half_px), min(meta.height, row + half_px)
    c0, c1 = max(0, col - half_px), min(meta.width, col + half_px)
    return ds.read(1, window=((r0, r1), (c0, c1)))


def crop_vir_confirmed(mosaic, lon, lat, half_px=VIR_WINDOW_PX) -> np.ndarray:
    line, sample = vir_lonlat_to_pixel(mosaic.label, lon, lat)
    line, sample = int(round(line)), int(round(sample))
    l0, l1 = max(0, line - half_px), min(mosaic.label.lines, line + half_px)
    s0, s1 = max(0, sample - half_px), min(mosaic.label.samples, sample + half_px)
    return mosaic.data[l0:l1, s0:s1]


def side_by_side(fc_arr: np.ndarray, vir_arr: np.ndarray, title: str, out_path: Path) -> None:
    fc_img = Image.fromarray(fc_arr).convert("L").resize((300, 300), Image.NEAREST)
    vir_img = Image.fromarray(normalize_for_display(vir_arr)).convert("L").resize((300, 300), Image.NEAREST)
    combined = Image.new("L", (300 * 2 + 10, 300 + 40), color=255)
    combined.paste(fc_img, (0, 40))
    combined.paste(vir_img, (310, 40))
    combined.save(out_path)
    print(f"Saved {out_path} (left=FC, right=VIR Band I center, confirmed lon_sign=-1) for {title}")


def main() -> int:
    vir_mosaic = read_vir_mosaic(VIR_BI_CENTER_PATH)
    fc_meta, fc_ds = open_fc_mosaic(FC_PATH)

    print("=== Longitude-sign determination (Rheasilvia diogenite signature) ===")
    sign_determination_check(vir_mosaic)

    print("\n=== Side-by-side crops at confirmed convention ===")
    for name, lon, lat in REFERENCE_POINTS:
        fc_crop = crop_fc(fc_ds, fc_meta, lon, lat)
        vir_crop = crop_vir_confirmed(vir_mosaic, lon, lat)
        print(f"{name} ({lon}E, {lat}): FC min={fc_crop.min()} max={fc_crop.max()} mean={fc_crop.mean():.1f}; "
              f"VIR valid_px={int(np.isfinite(vir_crop).sum())} mean={np.nanmean(vir_crop):.5f}")
        side_by_side(fc_crop, vir_crop, name, OUT_DIR / f"{name}_fc_vs_vir_confirmed.png")

    fc_ds.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
