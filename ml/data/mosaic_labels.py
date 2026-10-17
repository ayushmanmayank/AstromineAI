"""
Global-mosaic dataset: FIXED, COMMITTED label thresholds for Band I
center. Committed BEFORE any model is trained on them, per this
experiment's non-negotiable rule.

IMPORTANT, stated as plainly as this project's every other label-scheme
module: **these labels measure Band I (pyroxene absorption) center-
wavelength bins from the real VIR global mosaic raster. They are NOT a
validated mineral-composition classification.** No visual heuristic is
used anywhere -- every label comes only from the real VIR
VMT_MOSAIC-BI_CENTER_1.IMG raster (see ml/data/mosaic_reader.py).

Why tertiles, not this project's existing pointwise literature
thresholds (ml/data/spectral_labeling.py's BAND_I_THRESHOLDS_UM: 0.92,
0.95 -- diogenite-like / howardite-like / eucrite-like): checked
directly against this mosaic's real, full-globe valid-pixel
distribution (n=99,477,029 of 128,384,288 pixels, 77.5% valid) before
deciding, not assumed to transfer. Those pointwise thresholds, derived
from individual calibrated VIR spectra at specific crop locations,
produce a completely degenerate split on this HAMO+LAMO+HAMO-2-averaged
global mosaic: 1.14% / 98.86% / 0.00% -- essentially the entire planet
falls in one bucket. This is a real, reportable finding in its own
right (the global mosaic's Band I center dynamic range is far narrower
than single-point spectral extractions show -- plausibly because
multi-phase averaging smooths out the real but localized variation
individual spectra capture), not a reason to force the old thresholds.
Tertiles of this mosaic's own real distribution are used instead, giving
a genuinely balanced 3-way split; class names are deliberately neutral
(not diogenite/howardite/eucrite) so they are never mistaken for the
validated, literature-calibrated scheme used elsewhere in this project.

Real tertile cut points (33.333rd / 66.667th percentile of all valid
Band I center pixels in VMT_MOSAIC-BI_CENTER_1.IMG, computed once and
fixed here -- never recomputed per-split or per-run):
"""

from __future__ import annotations

import numpy as np

# Fixed, committed thresholds. Do not recompute from a subsequent run --
# if the source raster ever changes, this file must be regenerated
# deliberately and re-committed, with a note of why, same discipline as
# every other fixed threshold in this project (e.g.
# ml/data/spectral_labeling.py's BAND_I_THRESHOLDS_UM).
BAND_I_CENTER_TERTILE_1_UM = 0.925422728061676
BAND_I_CENTER_TERTILE_2_UM = 0.9275304079055786

CLASS_NAMES = ["band1_low", "band1_mid", "band1_high"]
NUM_CLASSES = len(CLASS_NAMES)

# Real class fractions at the thresholds above, over the full real global
# valid-pixel distribution (printed, not estimated, when this file was
# written): band1_low 33.25%, band1_mid 33.39%, band1_high 33.36%.


def classify_band1_center(value_um: float | np.ndarray) -> int | np.ndarray:
    """Returns the class index (0/1/2, see CLASS_NAMES) for a real Band I
    center value in microns. NaN input (nodata) returns -1 (no class)."""
    value_um = np.asarray(value_um)
    out = np.full(value_um.shape, -1, dtype=np.int8) if value_um.ndim else -1
    is_valid = np.isfinite(value_um)
    low = is_valid & (value_um < BAND_I_CENTER_TERTILE_1_UM)
    mid = is_valid & (value_um >= BAND_I_CENTER_TERTILE_1_UM) & (value_um < BAND_I_CENTER_TERTILE_2_UM)
    high = is_valid & (value_um >= BAND_I_CENTER_TERTILE_2_UM)

    if value_um.ndim == 0:
        if not is_valid:
            return -1
        if low:
            return 0
        if mid:
            return 1
        return 2

    out[low] = 0
    out[mid] = 1
    out[high] = 2
    return out
