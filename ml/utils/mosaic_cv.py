"""
Global-mosaic dataset v2: 5-fold region-block cross-validation with a
one-tile buffer.

Separate, new module (per this task's "new work goes in new files"
rule) built on top of ml/utils/mosaic_splits.py's existing
RegionBlock / region_block_for / is_buffered_out, reused here
unmodified -- same 20-degree block grid, same one-tile buffer rule, so
a tile that was buffered out of the original train/val/test split is
also buffered out of every CV fold here (never assigned to any fold).
ml/utils/mosaic_splits.py's own assign_block_splits() (a fixed 3-way
train/val/test split) is not reused directly for an N-way fold
partition -- assign_fold_blocks() below is a fresh, independent
generalization of its same greedy-deficit idea to N folds.

CV is now the PRIMARY metric for this v2 task: for each of n_folds
outer folds, that fold's tiles are the real test set (used exactly
once, as the outer test fold, never touched for tuning); one other
fold (rotating) is the inner validation fold (the only fold any
hyperparameter/model-selection decision may look at); every remaining
fold is training data. Every tile is some outer fold's test member
exactly once across the n_folds splits returned.

The original, fixed 222-tile Stage-3 test split
(datasets/mosaic/manifests/tile_manifest.csv's 'test' column) is left
completely untouched by this module and everything built on it -- it
is a different, already-spent test set from final/mosaic-dataset, not
reused here for tuning or for this v2 task's own CV metric.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

from ml.utils.mosaic_splits import RegionBlock, is_buffered_out, region_block_for

N_FOLDS = 5


def assign_fold_blocks(blocks: list[RegionBlock], n_folds: int, seed: int) -> dict[RegionBlock, int]:
    """Deterministically partitions every real unique region block into
    one of n_folds (0..n_folds-1), balanced by real tile counts (not
    bare block counts), via the same greedy-deficit approach as
    ml/utils/mosaic_splits.py's assign_block_splits() -- generalized
    here to N folds instead of a fixed train/val/test 3-way split."""
    if n_folds < 2:
        raise ValueError(f"n_folds must be >= 2, got {n_folds}")
    if not blocks:
        return {}

    counts: dict[RegionBlock, int] = defaultdict(int)
    for b in blocks:
        counts[b] += 1

    unique_blocks = list(counts.keys())
    rng = random.Random(seed)
    rng.shuffle(unique_blocks)

    n_total = len(blocks)
    target_per_fold = n_total / n_folds
    assigned = [0] * n_folds

    result: dict[RegionBlock, int] = {}
    for block in unique_blocks:
        deficits = [target_per_fold - assigned[f] for f in range(n_folds)]
        fold = max(range(n_folds), key=lambda f: deficits[f])
        result[block] = fold
        assigned[fold] += counts[block]

    return result


@dataclass(frozen=True)
class FoldSplit:
    fold_index: int
    train_idx: tuple[int, ...]
    val_idx: tuple[int, ...]
    test_idx: tuple[int, ...]


def make_cv_folds(
    lats: list[float],
    lons: list[float],
    block_size_deg: float,
    tile_size_deg: float,
    n_folds: int = N_FOLDS,
    seed: int = 42,
) -> list[FoldSplit]:
    """Builds n_folds real region-block CV folds over the given real
    tile centers (parallel lists; the int at position i in every
    returned index list refers to lats[i]/lons[i]).

    Buffer tiles (within one tile-width of a 20-deg grid boundary --
    same rule, same grid as ml/utils/mosaic_splits.py's
    is_buffered_out) are excluded from every fold entirely, exactly as
    Stage 3 excluded them from train/val/test.

    For outer fold i: test = fold i's tiles (used exactly once, as
    this fold's held-out test set); val = fold (i+1) % n_folds's tiles
    (an inner, rotating validation fold -- the only fold tuning may
    look at for this outer split, and never the outer test fold);
    train = every other fold's tiles.
    """
    n = len(lats)
    if n != len(lons):
        raise ValueError("lats and lons must be the same length")
    if n_folds < 2:
        raise ValueError(f"n_folds must be >= 2, got {n_folds}")

    keep_idx = [
        i for i in range(n)
        if not is_buffered_out(lats[i], lons[i] % 360.0, block_size_deg, tile_size_deg)
    ]
    blocks = [region_block_for(lats[i], lons[i], block_size_deg) for i in keep_idx]
    fold_map = assign_fold_blocks(blocks, n_folds, seed)

    idx_by_fold: list[list[int]] = [[] for _ in range(n_folds)]
    for local_i, global_i in enumerate(keep_idx):
        idx_by_fold[fold_map[blocks[local_i]]].append(global_i)

    folds = []
    for i in range(n_folds):
        test_idx = idx_by_fold[i]
        val_fold = (i + 1) % n_folds
        val_idx = idx_by_fold[val_fold]
        train_idx = [
            idx
            for f in range(n_folds)
            if f != i and f != val_fold
            for idx in idx_by_fold[f]
        ]
        folds.append(FoldSplit(
            fold_index=i,
            train_idx=tuple(train_idx),
            val_idx=tuple(val_idx),
            test_idx=tuple(test_idx),
        ))
    return folds
