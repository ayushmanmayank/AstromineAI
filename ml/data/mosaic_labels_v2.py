"""
Global-mosaic dataset v2, Stage 4 (optional task variant): a 2-class
task, defined and committed BEFORE any training on it, per this task's
own non-negotiable rule.

Reuses final/mosaic-dataset's already-fixed, already-committed Band I
center tertile thresholds (`ml/data/mosaic_labels.py`'s
`BAND_I_CENTER_TERTILE_1_UM` / `BAND_I_CENTER_TERTILE_2_UM`) rather
than computing new ones -- those thresholds are themselves a
committed, fixed Stage-1-5 result and are not touched here, only
imported. The 2-class task simply **drops the middle tertile**
(`band1_mid`) entirely and keeps the two extreme classes
(`band1_low`/`band1_high`), the simplest, most literature-defensible
2-way split of an already-fixed 3-way tertile scheme (the two classes
that are furthest apart in real Band I center value, hence least
likely to be a borderline/ambiguous case near a threshold).

This is reported as a SEPARATE task from the 3-class result throughout
this branch (never averaged or mixed into the same table), per this
task's own rule.
"""

from __future__ import annotations

import numpy as np

from ml.data.mosaic_labels import CLASS_NAMES as _TERTILE_CLASS_NAMES

CLASS_NAMES = ["band1_low", "band1_high"]
NUM_CLASSES = len(CLASS_NAMES)

# Index of each tertile class in ml.data.mosaic_labels.CLASS_NAMES, for
# the remap below -- read by name, not position, so this stays correct
# even if that module's class order is ever revisited (it is a
# committed, fixed file and will not be, but this is cheap insurance).
_LOW_IDX = _TERTILE_CLASS_NAMES.index("band1_low")
_MID_IDX = _TERTILE_CLASS_NAMES.index("band1_mid")
_HIGH_IDX = _TERTILE_CLASS_NAMES.index("band1_high")


def remap_tertile_to_2class(tertile_label: int | np.ndarray) -> int | np.ndarray:
    """Maps a real 3-class tertile label (from
    ml.data.mosaic_labels.classify_band1_center, -1/0/1/2) to this
    2-class task's label space: 0 = band1_low, 1 = band1_high, -1 =
    dropped (band1_mid, or original nodata/-1)."""
    arr = np.asarray(tertile_label)
    out = np.full(arr.shape, -1, dtype=np.int8) if arr.ndim else -1

    if arr.ndim == 0:
        if arr == _LOW_IDX:
            return 0
        if arr == _HIGH_IDX:
            return 1
        return -1

    out[arr == _LOW_IDX] = 0
    out[arr == _HIGH_IDX] = 1
    return out
