"""Tests for ml/data/mosaic_terranes.py and ml/utils/mosaic_terrane_cv.py
-- the global-mosaic v3 leave-one-terrane-out robustness check. Covers
this task's own rules: no overlap between train/test, the real >= 10
deg buffer is respected, and the split is deterministic."""

from __future__ import annotations

import pytest

from ml.data.mosaic_terranes import TERRANE_NAMES, TERRANES, terrane_for_lat
from ml.utils.mosaic_terrane_cv import MIN_BUFFER_DEG, make_terrane_folds


def test_terrane_for_lat_covers_full_range():
    # Every real latitude in [-90, 90] must map to exactly one of the
    # four named terranes -- no gaps.
    for lat in range(-90, 91):
        name = terrane_for_lat(float(lat))
        assert name in TERRANE_NAMES


def test_four_terranes_defined():
    assert len(TERRANES) == 4
    assert {t.name for t in TERRANES} == set(TERRANE_NAMES)


def test_buffer_below_minimum_rejected():
    with pytest.raises(ValueError):
        make_terrane_folds([0.0, 10.0], buffer_deg=5.0)


def test_no_overlap_between_train_and_test():
    lats = [float(lat) for lat in range(-90, 91)]
    folds = make_terrane_folds(lats, buffer_deg=10.0)
    for fold in folds:
        assert set(fold.train_idx).isdisjoint(set(fold.test_idx))


def test_every_tile_is_test_in_exactly_one_fold():
    lats = [float(lat) for lat in range(-90, 91)]
    folds = make_terrane_folds(lats, buffer_deg=10.0)
    all_test_idx = [idx for fold in folds for idx in fold.test_idx]
    assert len(all_test_idx) == len(set(all_test_idx))
    assert set(all_test_idx) == set(range(len(lats)))


def test_buffer_excludes_tiles_near_held_out_boundary():
    # southern_polar_cap's only real boundary is at -50 deg (its other
    # edge, -90, is the pole -- no training data beyond it to buffer).
    # A tile at -55 deg (5 deg from the boundary, inside the buffer)
    # must never appear in that fold's train set, even though it
    # belongs to a different terrane (southern_midlatitude_band).
    lats = [-80.0, -55.0, -45.0, -30.0, 0.0, 30.0, 60.0]
    folds = make_terrane_folds(lats, buffer_deg=10.0)
    polar_fold = next(f for f in folds if f.terrane_name == "southern_polar_cap")
    assert 1 not in polar_fold.train_idx  # index 1 = -55.0, within 10 deg of -50

    # A tile at -45 (5 deg on the OTHER side of the -50 boundary, but
    # itself inside southern_midlatitude_band, not southern_polar_cap)
    # should also be buffered out of the polar fold's train set.
    assert 2 not in polar_fold.train_idx  # index 2 = -45.0, within 10 deg of -50

    # A tile at -30 (20 deg from -50) is safely outside the buffer and
    # should be included.
    assert 3 in polar_fold.train_idx  # index 3 = -30.0


def test_buffer_respects_both_boundaries_of_a_middle_terrane():
    # southern_midlatitude_band has two real boundaries: -50 and -20.
    lats = [-55.0, -45.0, -25.0, -15.0, 0.0]
    folds = make_terrane_folds(lats, buffer_deg=10.0)
    mid_fold = next(f for f in folds if f.terrane_name == "southern_midlatitude_band")
    # -55 is within 10 deg of -50 -> buffered out.
    assert 0 not in mid_fold.train_idx
    # -15 is within 10 deg of -20 -> buffered out.
    assert 3 not in mid_fold.train_idx
    # 0.0 is safely outside both buffers (30 deg from -20) -> included.
    assert 4 in mid_fold.train_idx


def test_deterministic():
    lats = [float(lat) for lat in range(-90, 91, 3)]
    a = make_terrane_folds(lats, buffer_deg=10.0)
    b = make_terrane_folds(lats, buffer_deg=10.0)
    assert a == b


def test_larger_buffer_accepted():
    lats = [-80.0, -55.0, -30.0, 0.0, 30.0, 60.0]
    folds = make_terrane_folds(lats, buffer_deg=15.0)
    assert len(folds) == 4
