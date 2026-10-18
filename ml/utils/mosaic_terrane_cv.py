"""
Global-mosaic dataset v3, Stage 2 (Gate D): leave-one-terrane-out CV.

New, separate module (per this task's "new work goes in new files"
rule). Uses the real, committed terrane definitions in
`ml/data/mosaic_terranes.py` (not modified here, only imported).

For each of the four real terrane groups: train = every tile in the
OTHER three terranes, excluding any tile within `buffer_deg` (>= 10,
per this task's own rule) of the held-out terrane's real latitude
boundary -- so no training tile sits closer to the held-out region's
edge than the real buffer requires. test = every tile in the held-out
terrane itself. There is no inner validation split here (Stage 2
re-evaluates already-fixed model configurations from Stage 0/1; it does
not tune anything new).
"""

from __future__ import annotations

from dataclasses import dataclass

from ml.data.mosaic_terranes import TERRANES, terrane_for_lat

MIN_BUFFER_DEG = 10.0


@dataclass(frozen=True)
class TerraneFold:
    terrane_name: str
    train_idx: tuple[int, ...]
    test_idx: tuple[int, ...]


def make_terrane_folds(lats: list[float], buffer_deg: float = MIN_BUFFER_DEG) -> list[TerraneFold]:
    if buffer_deg < MIN_BUFFER_DEG:
        raise ValueError(f"buffer_deg must be >= {MIN_BUFFER_DEG} (got {buffer_deg})")

    terrane_of = [terrane_for_lat(lat) for lat in lats]
    folds = []
    for terrane in TERRANES:
        test_idx = [i for i, name in enumerate(terrane_of) if name == terrane.name]
        train_idx = []
        for i, (lat, name) in enumerate(zip(lats, terrane_of)):
            if name == terrane.name:
                continue
            too_close = False
            if terrane.lat_min_deg > -90.0 and abs(lat - terrane.lat_min_deg) < buffer_deg:
                too_close = True
            if terrane.lat_max_deg < 90.0 and abs(lat - terrane.lat_max_deg) < buffer_deg:
                too_close = True
            if not too_close:
                train_idx.append(i)
        folds.append(TerraneFold(
            terrane_name=terrane.name,
            train_idx=tuple(train_idx),
            test_idx=tuple(test_idx),
        ))
    return folds
