"""
Shared sample-metadata schema for AstroMineAI.

`SampleMetadata` is the single record type that describes one aligned
FC-image / VIR-spectrum region: enough provenance to trace every sample
back to its original PDS products, plus the fields the (not-yet-built)
labeling step and `src/data/dataset.py`'s `VestaDataset` will consume.

This module owns the schema. Other modules (spatial_alignment.py, the
future labeling step, dataset.py) import SampleMetadata rather than
redefining it, so the CSV column set stays consistent end to end.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Optional


@dataclass
class SampleMetadata:
    """One spatially-aligned FC image / VIR spectrum region.

    Provenance fields (mission, both instruments, both dataset IDs, both
    product IDs) are mandatory and are never left blank for a record that
    gets written out — see docs/scientific_integrity_checklist.md.
    """

    # Identity
    region_id: str

    # Provenance — required for every surviving sample
    mission: str
    image_instrument: str
    spectrum_instrument: str
    image_dataset_id: str
    spectrum_dataset_id: str
    image_product_id: str
    spectrum_product_id: str
    target: str

    # Geometry (Vesta body-fixed lat/lon, degrees) of the *overlap region*
    min_latitude: float
    max_latitude: float
    west_longitude: float
    east_longitude: float
    center_latitude: float
    center_longitude: float

    # Timing
    image_start_time: str
    spectrum_start_time: str
    time_delta_seconds: float

    # Correspondence quality
    spatial_iou: float
    correspondence_confidence: float

    # Data locations
    image_path: str            # cropped region PNG under datasets/processed/
    spectrum_path: str         # original .QUB under datasets/raw/ (untouched)
    image_label_path: str      # original FC .LBL under datasets/raw/ (untouched)
    spectrum_label_path: str   # original VIR .LBL under datasets/raw/ (untouched)

    # Labeling — "unlabeled" / "pending" is the intentional placeholder
    # state produced by spatial_alignment.py. Compositional labels require
    # the Month 1 data audit + label scheme decision (see
    # docs/month1_log.md, Slice 3), which comes after seeing how many
    # independent regions survive alignment.
    label: str = "unlabeled"
    label_source: str = "pending"

    # Dataset split, assigned by ml/utils/splits.py's
    # assign_region_based_splits(). "unassigned" is the placeholder state
    # before splitting has run.
    split: str = "unassigned"

    # label_source strings that are never acceptable on a *labeled* row —
    # generic enough to hide that no real, reproducible rule was applied.
    # See docs/scientific_integrity_checklist.md: every label_source must
    # name the exact rule/thresholds used.
    _BANNED_LABEL_SOURCES = frozenset({
        "", "heuristic", "pending", "unknown", "manual", "eyeball",
        "eyeballed", "guess", "n/a", "na", "tbd", "unlabeled",
    })
    _VALID_SPLITS = frozenset({"train", "val", "test", "unassigned"})

    def validate(self) -> None:
        """Raise ValueError if this record is internally inconsistent or
        carries a label_source that isn't specific/reproducible.

        Called by write_metadata_csv() on every record — this is meant to
        make it structurally hard to write out a row with a label that
        has no auditable, reproducible source.
        """
        required_provenance = {
            "mission": self.mission, "image_instrument": self.image_instrument,
            "spectrum_instrument": self.spectrum_instrument,
            "image_dataset_id": self.image_dataset_id,
            "spectrum_dataset_id": self.spectrum_dataset_id,
            "image_product_id": self.image_product_id,
            "spectrum_product_id": self.spectrum_product_id,
        }
        for field_name, value in required_provenance.items():
            if not value:
                raise ValueError(f"{self.region_id}: missing required provenance field {field_name!r}")

        if self.label == "unlabeled":
            if self.label_source != "pending":
                raise ValueError(
                    f"{self.region_id}: label is 'unlabeled' but label_source is "
                    f"{self.label_source!r} (expected 'pending')"
                )
        else:
            source_key = self.label_source.strip().lower()
            if source_key in self._BANNED_LABEL_SOURCES:
                raise ValueError(
                    f"{self.region_id}: label_source {self.label_source!r} is too generic "
                    f"to be reproducible/auditable for a labeled row (label={self.label!r})"
                )
            if len(self.label_source.strip()) < 8:
                raise ValueError(
                    f"{self.region_id}: label_source {self.label_source!r} is too short to "
                    f"identify a specific rule/threshold set"
                )

        if self.split not in self._VALID_SPLITS:
            raise ValueError(f"{self.region_id}: split {self.split!r} is not one of {sorted(self._VALID_SPLITS)}")


_FIELD_NAMES = [f.name for f in fields(SampleMetadata)]
_FLOAT_FIELDS = {
    "min_latitude", "max_latitude", "west_longitude", "east_longitude",
    "center_latitude", "center_longitude", "time_delta_seconds",
    "spatial_iou", "correspondence_confidence",
}


def read_metadata_csv(in_path: str | Path) -> list[SampleMetadata]:
    """Read sample_metadata.csv back into SampleMetadata records.

    Does NOT call validate() on read — a file may legitimately hold
    'unlabeled'/'pending' placeholder rows mid-pipeline. Callers that need
    guaranteed-valid records should validate() explicitly.
    """
    in_path = Path(in_path)
    if not in_path.exists():
        return []
    records = []
    with open(in_path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            kwargs = {}
            for key, value in row.items():
                kwargs[key] = float(value) if key in _FLOAT_FIELDS else value
            records.append(SampleMetadata(**kwargs))
    return records


def write_metadata_csv(records: list[SampleMetadata], out_path: str | Path) -> None:
    """Validate and write SampleMetadata records to a CSV, creating parent
    dirs as needed.

    Every record is validated (record.validate()) before anything is
    written — a single invalid row aborts the whole write rather than
    silently writing a partially-bad file.

    Overwrites `out_path` with exactly the given records (not append) —
    callers are expected to pass the full current set of surviving samples.
    """
    for record in records:
        record.validate()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELD_NAMES)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))
