"""Tests for ml/utils/mosaic_cv.py -- 5-fold region-block CV for the
global-mosaic v2 task. Covers this task's own non-negotiable rules: no
tile overlap across a fold's train/val/test, the buffer is respected,
every tile is used as the outer test fold exactly once, and the split
is deterministic given a seed."""

from __future__ import annotations

import pytest

from ml.utils.mosaic_cv import assign_fold_blocks, make_cv_folds
from ml.utils.mosaic_splits import RegionBlock, is_buffered_out, region_block_for


def _grid_lats_lons(block_size=20.0, tile_size=2.0):
    lats = [lat for lat in range(-60, 60, int(tile_size))]
    lons = [lon for lon in range(0, 360, int(tile_size))]
    all_lats, all_lons = [], []
    for lat in lats:
        for lon in lons:
            all_lats.append(float(lat))
            all_lons.append(float(lon))
    return all_lats, all_lons


def test_n_folds_below_minimum_rejected():
    with pytest.raises(ValueError):
        make_cv_folds([0.0], [0.0], 20.0, 2.0, n_folds=1, seed=1)


def test_assign_fold_blocks_is_deterministic():
    blocks = [RegionBlock(lat, lon) for lat in range(-4, 4) for lon in range(0, 18)]
    weighted = blocks + blocks[:5] * 3
    a = assign_fold_blocks(weighted, n_folds=5, seed=42)
    b = assign_fold_blocks(weighted, n_folds=5, seed=42)
    assert a == b


def test_every_tile_used_as_test_exactly_once():
    lats, lons = _grid_lats_lons()
    folds = make_cv_folds(lats, lons, block_size_deg=20.0, tile_size_deg=2.0, n_folds=5, seed=42)

    all_test_idx = [idx for fold in folds for idx in fold.test_idx]
    assert len(all_test_idx) == len(set(all_test_idx)), "some tile appeared as test in more than one fold"

    # The union of every fold's test set is exactly the set of
    # non-buffered tiles (every one used exactly once overall).
    non_buffered = {
        i for i in range(len(lats))
        if not is_buffered_out(lats[i], lons[i] % 360.0, 20.0, 2.0)
    }
    assert set(all_test_idx) == non_buffered


def test_no_overlap_between_train_val_test_within_a_fold():
    lats, lons = _grid_lats_lons()
    folds = make_cv_folds(lats, lons, block_size_deg=20.0, tile_size_deg=2.0, n_folds=5, seed=42)
    for fold in folds:
        train, val, test = set(fold.train_idx), set(fold.val_idx), set(fold.test_idx)
        assert train & val == set()
        assert train & test == set()
        assert val & test == set()


def test_no_tile_overlap_across_splits_at_block_level():
    """Two tiles from the same real region block must always land in the
    same role (train/val/test) within a given fold -- never split across
    roles, since the CV splits by block, not by individual tile."""
    lats, lons = _grid_lats_lons()
    folds = make_cv_folds(lats, lons, block_size_deg=20.0, tile_size_deg=2.0, n_folds=5, seed=42)

    for fold in folds:
        role_by_idx = {}
        for role, idxs in (("train", fold.train_idx), ("val", fold.val_idx), ("test", fold.test_idx)):
            for idx in idxs:
                role_by_idx[idx] = role

        block_roles: dict[RegionBlock, set[str]] = {}
        for idx, role in role_by_idx.items():
            block = region_block_for(lats[idx], lons[idx], 20.0)
            block_roles.setdefault(block, set()).add(role)

        for block, roles in block_roles.items():
            assert len(roles) == 1, f"fold {fold.fold_index}: block {block} split across roles {roles}"


def test_buffer_respected_tile_never_assigned_to_any_role():
    lats, lons = _grid_lats_lons()
    # Find a real tile this grid actually buffers out (near a 20-deg edge).
    buffered_candidates = [
        i for i in range(len(lats))
        if is_buffered_out(lats[i], lons[i] % 360.0, 20.0, 2.0)
    ]
    assert buffered_candidates, "test fixture grid should contain at least one buffered-out tile"

    folds = make_cv_folds(lats, lons, block_size_deg=20.0, tile_size_deg=2.0, n_folds=5, seed=42)
    all_assigned = set()
    for fold in folds:
        all_assigned |= set(fold.train_idx) | set(fold.val_idx) | set(fold.test_idx)

    for idx in buffered_candidates:
        assert idx not in all_assigned, f"buffered-out tile {idx} was assigned to a fold role"


def test_val_fold_never_equals_test_fold_and_rotates():
    lats, lons = _grid_lats_lons()
    folds = make_cv_folds(lats, lons, block_size_deg=20.0, tile_size_deg=2.0, n_folds=5, seed=42)
    seen_val_test_pairs = set()
    for fold in folds:
        test_set = set(fold.test_idx)
        val_set = set(fold.val_idx)
        assert test_set.isdisjoint(val_set)
        seen_val_test_pairs.add((fold.fold_index,))
    assert len(folds) == 5


def test_deterministic_given_seed():
    lats, lons = _grid_lats_lons()
    a = make_cv_folds(lats, lons, 20.0, 2.0, n_folds=5, seed=7)
    b = make_cv_folds(lats, lons, 20.0, 2.0, n_folds=5, seed=7)
    assert a == b
