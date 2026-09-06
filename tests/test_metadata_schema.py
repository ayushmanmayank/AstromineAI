"""Tests for ml/utils/metadata_schema.py's SampleMetadata.validate()."""

from __future__ import annotations

import pytest

from ml.utils.metadata_schema import SampleMetadata


def _make_record(**overrides) -> SampleMetadata:
    defaults = dict(
        region_id="r1",
        mission="DAWN",
        image_instrument="FC2",
        spectrum_instrument="VIR-IR",
        image_dataset_id="DAWN-A-FC2-3-RDR-VESTA-IMAGES-V1.0",
        spectrum_dataset_id="DAWN-A-VIR-3-RDR-IR-VESTA-SPECTRA-V1.0",
        image_product_id="0001898",
        spectrum_product_id="VIR_IR_1B_1_399216227",
        target="VESTA",
        min_latitude=-10.0, max_latitude=0.0,
        west_longitude=150.0, east_longitude=140.0,
        center_latitude=-5.0, center_longitude=145.0,
        image_start_time="2011-123T13:35:16.604",
        spectrum_start_time="2011-123T13:35:20.000",
        time_delta_seconds=3.4,
        spatial_iou=0.5, correspondence_confidence=0.6,
        image_path="datasets/processed/r1.png",
        spectrum_path="datasets/raw/dawn_vir_vesta/x.QUB",
        image_label_path="datasets/raw/dawn_fc_vesta/x.LBL",
        spectrum_label_path="datasets/raw/dawn_vir_vesta/x.LBL",
    )
    defaults.update(overrides)
    return SampleMetadata(**defaults)


def test_unlabeled_pending_is_valid():
    record = _make_record(label="unlabeled", label_source="pending")
    record.validate()  # should not raise


def test_unlabeled_with_nonpending_source_is_rejected():
    record = _make_record(label="unlabeled", label_source="something else")
    with pytest.raises(ValueError):
        record.validate()


@pytest.mark.parametrize(
    "banned_source",
    ["", "heuristic", "pending", "unknown", "manual", "eyeball", "eyeballed", "guess", "n/a", "HEURISTIC"],
)
def test_labeled_row_rejects_generic_label_source(banned_source):
    record = _make_record(label="eucrite_like", label_source=banned_source)
    with pytest.raises(ValueError):
        record.validate()


def test_labeled_row_rejects_too_short_label_source():
    record = _make_record(label="eucrite_like", label_source="v1")
    with pytest.raises(ValueError):
        record.validate()


def test_labeled_row_accepts_specific_label_source():
    record = _make_record(
        label="eucrite_like",
        label_source="VIR IR Band II (~1.9-2.0um) center-wavelength threshold, VIR band-center threshold v1",
    )
    record.validate()  # should not raise


@pytest.mark.parametrize("missing_field", [
    "mission", "image_instrument", "spectrum_instrument",
    "image_dataset_id", "spectrum_dataset_id", "image_product_id", "spectrum_product_id",
])
def test_missing_provenance_field_is_rejected(missing_field):
    record = _make_record(**{missing_field: ""})
    with pytest.raises(ValueError):
        record.validate()


def test_invalid_split_is_rejected():
    record = _make_record(label="unlabeled", label_source="pending", split="not_a_real_split")
    with pytest.raises(ValueError):
        record.validate()


@pytest.mark.parametrize("valid_split", ["train", "val", "test", "unassigned"])
def test_valid_splits_are_accepted(valid_split):
    record = _make_record(label="unlabeled", label_source="pending", split=valid_split)
    record.validate()  # should not raise
