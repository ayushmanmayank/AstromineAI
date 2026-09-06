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
    _time_proximity_factor,
    compute_footprint_overlap,
    compute_size_ratio_penalty,
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

# The real best/calibration pair from Slice 7/8's diagnosis (a different FC
# frame than FC_RAW above, ~5 min later in the same nadir track — this one
# genuinely overlaps VIR_RAW's footprint):
#   datasets/raw/dawn_fc_vesta/DWNVFC2_1B/DATA/FITS/2011272_HAMO/2011272_CYCLE1/
#     2011272_C1_ORBIT01/FC21B0007112_....LBL
FC_CALIBRATION = dict(
    product_id="0007112", instrument_id="FC2", start_time="2011-273T01:05:53.107",
    min_lat=-17.7690614559, max_lat=0.9702601299,
    raw_west_lon=82.8406283772, raw_east_lon=101.6085567462,
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


# --------------------------------------------------------------------------
# Regression tests for the size-ratio specificity penalty (Month 1, Slice 8).
#
# Calibrated against the real distribution across all 1600 real HAMO-cycle-1
# FC/VIR candidate pairs: every one has a footprint-area ratio between 1.88x
# and 4.04x (median 2.23x) -- see docs/month1_log.md, Slice 8, for the full
# table. SIZE_RATIO_NO_PENALTY_THRESHOLD=5.0 was picked because it sits
# comfortably above that observed real max, not because it makes any
# specific pair cross the 0.30 survivor threshold -- these tests assert the
# threshold's real consequences, not a target.
# --------------------------------------------------------------------------


def test_size_ratio_penalty_is_unity_within_the_real_observed_range():
    """No real HAMO-cycle-1 FC/VIR pair exceeds a 4.04x size ratio -- the
    whole real range must get zero discount."""
    assert compute_size_ratio_penalty(1.0) == pytest.approx(1.0)
    assert compute_size_ratio_penalty(1.88) == pytest.approx(1.0)  # observed real min
    assert compute_size_ratio_penalty(2.23) == pytest.approx(1.0)  # observed real median
    assert compute_size_ratio_penalty(4.04) == pytest.approx(1.0)  # observed real max
    assert compute_size_ratio_penalty(5.0) == pytest.approx(1.0)   # the threshold itself


def test_size_ratio_penalty_decays_beyond_the_threshold():
    """Ratios genuinely outside what real Dawn FC/VIR HAMO pairs exhibit
    (e.g. a full-disk mosaic accidentally compared against a narrow VIR
    scan) should still be discounted -- the underlying specificity concern
    is real, just recalibrated to where it actually applies."""
    assert compute_size_ratio_penalty(10.0) == pytest.approx(0.5)
    assert compute_size_ratio_penalty(50.0) == pytest.approx(0.1)
    assert compute_size_ratio_penalty(0.0) == pytest.approx(0.0)


def test_calibration_pair_confidence_lands_near_0_305_as_a_consequence():
    """The real calibration pair (FC 0007112 / VIR VIR_VIS_1B_1_370617178,
    size_ratio=1.93x, overlap_coefficient=0.305, ~6 minutes apart) should
    now score close to its overlap_coefficient (0.305), since a 1.93x
    ratio is well inside the no-penalty range and gets essentially no
    discount -- crossing the existing 0.30 survivor threshold is a
    consequence of that, not a target this test was reverse-tuned to hit
    exactly."""
    fc_west, fc_east = _standardize_footprint_lon(FC_CALIBRATION["raw_west_lon"], FC_CALIBRATION["raw_east_lon"], "FC2")
    vir_west, vir_east = _standardize_footprint_lon(VIR_RAW["raw_west_lon"], VIR_RAW["raw_east_lon"], "VIR")
    fc_geom = _make_geometry(FC_CALIBRATION, fc_west, fc_east)
    vir_geom = _make_geometry(VIR_RAW, vir_west, vir_east)

    details = _footprint_overlap_details(fc_geom.footprint, vir_geom.footprint)
    assert details is not None
    assert details["size_ratio"] == pytest.approx(1.93, abs=0.01)
    assert details["overlap_coefficient"] == pytest.approx(0.305, abs=0.001)

    penalty = compute_size_ratio_penalty(details["size_ratio"])
    assert penalty == pytest.approx(1.0)  # within the no-penalty range -- no discount

    confidence = compute_footprint_overlap(fc_geom, vir_geom, max_time_delta_hours=24.0)
    assert confidence is not None
    # overlap_coefficient (0.305) barely discounted by the near-1.0 time
    # factor (~6 min apart, well inside the 24h window) -- lands near
    # 0.305, comfortably (if narrowly) above the existing 0.30 threshold.
    assert confidence == pytest.approx(0.3046, abs=0.001)
    assert confidence > 0.30
