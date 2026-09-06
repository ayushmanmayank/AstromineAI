"""
Region-based train/val/test splitting for AstroMineAI.

"Region-based" means the split unit is a *spatial region group*, not an
individual sample: samples whose overlap footprints are near each other
on Vesta are grouped together and assigned to the same split as a block.
Splitting by individual sample instead would let near-duplicate, spatially
adjacent crops leak between train and test — the model could learn to
recognize a specific patch of terrain rather than compositional signal.

This module only assigns `.split` on SampleMetadata records already
produced by spatial_alignment.py — it does not touch spatial alignment,
labeling, or acquisition.
"""

from __future__ import annotations

import logging
import math
import random
from collections import defaultdict
from typing import Optional

from ml.utils.metadata_schema import SampleMetadata

logger = logging.getLogger("splits")


def _region_group_key(record: SampleMetadata, bin_size_degrees: float) -> tuple[int, int]:
    """Coarse spatial bin for a record's overlap-region center, used to
    group nearby samples so they land in the same split.

    A fixed-size lat/lon grid is a simple, auditable choice — not a
    clustering algorithm with hidden parameters. `bin_size_degrees` should
    be large enough that FC's single-frame footprint (a few degrees on
    Vesta at HAMO/LAMO range) can't straddle two bins in a way that splits
    one physical region across train and test.
    """
    lat_bin = math.floor(record.center_latitude / bin_size_degrees)
    lon_bin = math.floor(record.center_longitude / bin_size_degrees)
    return (lat_bin, lon_bin)


def assign_region_based_splits(
    records: list[SampleMetadata],
    train_frac: float,
    val_frac: float,
    test_frac: float,
    seed: int = 42,
    bin_size_degrees: float = 5.0,
) -> list[SampleMetadata]:
    """Assign `.split` ('train'/'val'/'test') to every record, in place,
    keeping spatially-grouped regions together. Returns the same list
    (mutated) for convenience.

    Splitting logic:
      1. Group records into region groups by a coarse lat/lon bin over
         each record's overlap-region center.
      2. Shuffle the *groups* (not individual records) deterministically
         by `seed`.
      3. Walk the shuffled groups, assigning each whole group to
         train/val/test greedily by remaining target sample counts, so
         the realized split sizes track train_frac/val_frac/test_frac as
         closely as group sizes allow.

    With very few records (as of Month 1 Slice 3: zero), this reduces to
    a no-op — logged, not silently skipped.
    """
    if abs((train_frac + val_frac + test_frac) - 1.0) > 1e-6:
        raise ValueError(
            f"train_frac + val_frac + test_frac must sum to 1.0, got "
            f"{train_frac} + {val_frac} + {test_frac} = {train_frac + val_frac + test_frac}"
        )

    if not records:
        logger.warning(
            "assign_region_based_splits() called with 0 records — nothing to split. "
            "Returning an empty list rather than fabricating split assignments."
        )
        return records

    groups: dict[tuple[int, int], list[SampleMetadata]] = defaultdict(list)
    for record in records:
        groups[_region_group_key(record, bin_size_degrees)].append(record)

    group_keys = list(groups.keys())
    rng = random.Random(seed)
    rng.shuffle(group_keys)

    n_total = len(records)
    targets = {
        "train": train_frac * n_total,
        "val": val_frac * n_total,
        "test": test_frac * n_total,
    }
    assigned_counts = {"train": 0, "val": 0, "test": 0}

    for key in group_keys:
        group_records = groups[key]
        # Assign this whole group to whichever split is furthest below its
        # target share (in absolute sample count), so groups of very
        # different sizes still converge toward the requested fractions.
        deficits = {
            split: targets[split] - assigned_counts[split]
            for split in ("train", "val", "test")
        }
        target_split = max(deficits, key=deficits.get)
        for record in group_records:
            record.split = target_split
        assigned_counts[target_split] += len(group_records)

    logger.info(
        "Assigned %d records across %d region groups (bin=%.1f deg) to splits: %s "
        "(target fractions train=%.2f val=%.2f test=%.2f)",
        n_total, len(group_keys), bin_size_degrees, assigned_counts,
        train_frac, val_frac, test_frac,
    )
    return records
