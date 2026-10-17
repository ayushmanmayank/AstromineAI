"""
Global-mosaic dataset: region-block train/val/test splitting.

Deliberately separate from ml/utils/splits.py (this project's existing
region-based splitter for the real FC/VIR crop pipeline) -- different
data shape (a tiled global mosaic, not FC-crop/VIR-spectrum pairs),
different, larger block size (this experiment's own rule: blocks must be
>= 20 degrees lat/lon, big enough that no single named geologic feature
realistically straddles a split boundary at useful scale), and a real
buffer requirement (a one-tile gap between adjacent blocks' assigned
tiles) that ml/utils/splits.py's spatial grouping does not implement.

Splitting unit is the BLOCK, never the individual tile: every tile
inside a block goes to that block's assigned split, so there is no way
for two tiles from the same 20-degree region to land in different
splits -- the random-tile-split this experiment's rules explicitly
forbid.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

MIN_BLOCK_SIZE_DEG = 20.0


@dataclass(frozen=True)
class RegionBlock:
    lat_block: int
    lon_block: int


def region_block_for(lat_deg: float, lon_deg: float, block_size_deg: float = MIN_BLOCK_SIZE_DEG) -> RegionBlock:
    if block_size_deg < MIN_BLOCK_SIZE_DEG:
        raise ValueError(f"block_size_deg must be >= {MIN_BLOCK_SIZE_DEG} (got {block_size_deg})")
    lon_wrapped = lon_deg % 360.0
    return RegionBlock(
        lat_block=math.floor(lat_deg / block_size_deg),
        lon_block=math.floor(lon_wrapped / block_size_deg),
    )


def assign_block_splits(
    blocks: list[RegionBlock],
    train_frac: float,
    val_frac: float,
    test_frac: float,
    seed: int,
) -> dict[RegionBlock, str]:
    """Deterministically assigns every real region block (by real tile
    counts, not just block counts, so split sizes actually track the
    requested fractions) to 'train'/'val'/'test'. Mirrors
    ml/utils/splits.py's greedy-by-remaining-deficit approach (same
    project convention) -- a fresh, independent implementation since this
    is a new, separate module per this task's own instruction, not an
    edit of the existing one.
    """
    if abs((train_frac + val_frac + test_frac) - 1.0) > 1e-6:
        raise ValueError(
            f"train_frac + val_frac + test_frac must sum to 1.0, got "
            f"{train_frac} + {val_frac} + {test_frac} = {train_frac + val_frac + test_frac}"
        )
    if not blocks:
        return {}

    counts: dict[RegionBlock, int] = defaultdict(int)
    for b in blocks:
        counts[b] += 1

    unique_blocks = list(counts.keys())
    rng = random.Random(seed)
    rng.shuffle(unique_blocks)

    n_total = len(blocks)
    targets = {"train": train_frac * n_total, "val": val_frac * n_total, "test": test_frac * n_total}
    assigned = {"train": 0, "val": 0, "test": 0}

    result: dict[RegionBlock, str] = {}
    for block in unique_blocks:
        deficits = {split: targets[split] - assigned[split] for split in ("train", "val", "test")}
        target_split = max(deficits, key=deficits.get)
        result[block] = target_split
        assigned[target_split] += counts[block]

    return result


def is_buffered_out(
    lat_deg: float,
    lon_deg: float,
    block_size_deg: float,
    tile_size_deg: float,
) -> bool:
    """True if (lat, lon) falls within one tile-width of a region-block
    boundary -- such tiles are dropped entirely (assigned to no split),
    so no tile near a split boundary can leak context across it."""
    lat_in_block = lat_deg % block_size_deg
    lon_in_block = lon_deg % block_size_deg
    near_lat_edge = lat_in_block < tile_size_deg or (block_size_deg - lat_in_block) < tile_size_deg
    near_lon_edge = lon_in_block < tile_size_deg or (block_size_deg - lon_in_block) < tile_size_deg
    return near_lat_edge or near_lon_edge
