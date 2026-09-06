"""
Regression test for the FC/VIR longitude-convention bug (Month 1, Slice 7).

Built from a real diagnosed pair: FC product 0007106 (real HAMO frame) and
VIR product VIR_VIS_1B_1_370617178 (real HAMO cube), ~2h10m apart, with
real latitude overlap. Before the fix, the previous version of
`_lon_to_x()` (which applied one uniform "west-positive" transform,
inferred from VIR-only evidence) inflated FC's true ~18.69 degree
longitude span to a computed ~341.31 degree span, crushing this pair's
overlap toward zero. See docs/month1_log.md, Slice 7, for the full
evidence (20/20 real-sample verification per instrument + SIS doc quotes)
behind the fix in `_standardize_footprint_lon()`.
"""

from __future__ import annotations

import pytest

from ml.data.spatial_alignment import (
    ProductGeometry,
    _footprint_overlap_details,
    _standardize_footprint_lon,
)

# Real values, taken directly from the two real downloaded .LBL files:
#   datasets/raw/dawn_fc_vesta/DWNVFC2_1B/DATA/FITS/2011272_HAMO/2011272_CYCLE1/
#     2011272_C1_ORBIT01/FC21B0007106_11273010035F8G.LBL
#   datasets/raw/dawn_vir_vesta/DWNVVIR_V1B/DATA/20110929_HAMO/20110929_CYCLE1/
#     VIR_VIS_1B_1_370617178_2.LBL
FC_RAW = dict(
    product_id="0007106", instrument_id="FC2", start_time="2011-273T01:00:35.107",
    min_lat=-15.1332524090, max_lat=3.6439840707,
    raw_west_lon=89.0089253108, raw_east_lon=107.6987994337,
)
VIR_RAW = dict(
    product_id="VIR_VIS_1B_1_370617178", instrument_id="VIR", start_time="2011-09-30T01:11:51.748",
    min_lat=-19.915, max_lat=-7.685,
    raw_west_lon=88.343, raw_east_lon=73.480,
)


def _make_geometry(raw: dict, west_lon: float, east_lon: float) -> ProductGeometry:
    return ProductGeometry(
        label_path="<fixture>",
        product_id=raw["product_id"],
        dataset_id="<fixture>",
        instrument_id=raw["instrument_id"],
        instrument_host="DAWN",
        mission_name="DAWN",
        target_name="4 VESTA",
        start_time=raw["start_time"],
        stop_time=raw["start_time"],
        footprint={
            "min_lat": raw["min_lat"], "max_lat": raw["max_lat"],
            "west_lon": west_lon, "east_lon": east_lon,
        },
        footprint_source="bounding_box",
    )


def test_fc_longitude_standardization_is_identity():
    """FC's raw WESTERNMOST/EASTERNMOST_LONGITUDE are already standard
    (increasing-eastward) — confirmed by FC's own SIS ("planetocentric
    east longitude") and by 20/20 real HAMO samples. Standardization must
    not alter them."""
    west, east = _standardize_footprint_lon(FC_RAW["raw_west_lon"], FC_RAW["raw_east_lon"], "FC2")
    assert west == pytest.approx(FC_RAW["raw_west_lon"])
    assert east == pytest.approx(FC_RAW["raw_east_lon"])


def test_vir_longitude_standardization_swaps():
    """VIR's raw fields empirically behave as west-positive (20/20 real
    HAMO samples: WESTERNMOST > EASTERNMOST, CENTER always between) --
    standardizing must swap them onto the increasing-eastward frame FC
    already uses."""
    west, east = _standardize_footprint_lon(VIR_RAW["raw_west_lon"], VIR_RAW["raw_east_lon"], "VIR")
    assert west == pytest.approx(VIR_RAW["raw_east_lon"])
    assert east == pytest.approx(VIR_RAW["raw_west_lon"])
    assert west < east


def test_fc_true_longitude_span_is_not_inflated():
    """The core regression: FC's real footprint span is ~18.69 degrees.
    Before the fix, applying a uniform VIR-shaped transform to FC's
    already-standard values inflated this to ~341.31 degrees (an 18.3x
    distortion, verified by direct computation during diagnosis). After
    the fix, FC's standardized values must reproduce the true span."""
    west, east = _standardize_footprint_lon(FC_RAW["raw_west_lon"], FC_RAW["raw_east_lon"], "FC2")

    true_span = FC_RAW["raw_east_lon"] - FC_RAW["raw_west_lon"]
    assert true_span == pytest.approx(18.69, abs=0.01)

    computed_span = (east - west) % 360.0
    assert computed_span == pytest.approx(18.69, abs=0.01)
    assert computed_span < 180.0  # sanity: never more than one hemisphere
    assert computed_span != pytest.approx(341.31, abs=1.0)  # the pre-fix, buggy value

    # Self-overlap sanity check via the real overlap-scoring function.
    fc_geom = _make_geometry(FC_RAW, west, east)
    details = _footprint_overlap_details(fc_geom.footprint, fc_geom.footprint)
    assert details is not None
    assert details["iou"] == pytest.approx(1.0, abs=1e-9)
    assert details["size_ratio"] == pytest.approx(1.0, abs=1e-9)


def test_real_fc_vir_pair_is_correctly_adjacent_not_overlapping():
    """The actual diagnosed pair, re-checked honestly rather than assumed
    to overlap just because it scored highest under the old bug: once
    BOTH footprints are correctly standardized, FC covers longitude
    89.01-107.70 and VIR covers 73.48-88.34 -- adjacent, with a real
    ~0.67 degree gap, not actual overlap. The fix's job is to report this
    real geometry correctly (a small, genuine gap), not to manufacture
    overlap where standardized data shows none. Real latitude DOES
    overlap (7.45 deg) -- it's specifically the longitude that falls just
    short here, for this one pair."""
    fc_west, fc_east = _standardize_footprint_lon(FC_RAW["raw_west_lon"], FC_RAW["raw_east_lon"], "FC2")
    vir_west, vir_east = _standardize_footprint_lon(VIR_RAW["raw_west_lon"], VIR_RAW["raw_east_lon"], "VIR")
    assert vir_east == pytest.approx(88.343, abs=0.001)
    assert fc_west == pytest.approx(89.009, abs=0.001)
    assert fc_west - vir_east == pytest.approx(0.666, abs=0.01)  # the real gap

    fc_geom = _make_geometry(FC_RAW, fc_west, fc_east)
    vir_geom = _make_geometry(VIR_RAW, vir_west, vir_east)
    details = _footprint_overlap_details(fc_geom.footprint, vir_geom.footprint)
    assert details is not None
    assert details["overlap_coefficient"] == pytest.approx(0.0)  # correctly zero, not fabricated
