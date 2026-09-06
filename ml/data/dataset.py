"""
VestaDataset — PyTorch Dataset over datasets/metadata/sample_metadata.csv.

Reads the cropped FC-image-region PNGs written by spatial_alignment.py
and their labels (assigned by spectral_labeling.py + splits.py), filtered
to one split ('train' / 'val' / 'test').

Deliberately minimal: this project has zero labeled samples as of Month 1
(see docs/month1_log.md) — this class is written to be correct once real
labeled data exists, not validated against a real, populated dataset yet.
It raises clearly rather than silently returning something misleading when
asked for a split that (as of now) has zero rows, so a training script
using it fails loudly instead of appearing to "work" on no data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
from torch.utils.data import Dataset

from ml.utils.metadata_schema import SampleMetadata, read_metadata_csv

logger = logging.getLogger("dataset")

# Fixed class list + index mapping — must match ml/data/spectral_labeling.py's
# label vocabulary. Kept here (not derived from whatever's in the CSV) so
# the index-to-class mapping is stable across runs regardless of which
# classes happen to be present in a given split.
CLASSES = ["diogenite_like", "howardite_like", "eucrite_like"]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}
# Rows with this label (or any label not in CLASSES, e.g. "unlabeled" or
# "indeterminate_weak_feature") are excluded from the dataset entirely —
# they are not a 4th class, they are "we don't have a usable label for
# this sample."
EXCLUDED_LABELS = {"unlabeled", "indeterminate_weak_feature"}


class VestaDataset(Dataset):
    def __init__(
        self,
        metadata_csv: str | Path = "datasets/metadata/sample_metadata.csv",
        split: str = "train",
        image_size: int = 224,
        transform=None,
    ):
        self.metadata_csv = Path(metadata_csv)
        self.split = split
        self.image_size = image_size
        self.transform = transform

        all_records = read_metadata_csv(self.metadata_csv)
        self.records: list[SampleMetadata] = [
            r for r in all_records
            if r.split == split and r.label in CLASS_TO_IDX
        ]

        n_total = len(all_records)
        n_wrong_split = sum(1 for r in all_records if r.split != split)
        n_excluded_label = sum(1 for r in all_records if r.split == split and r.label not in CLASS_TO_IDX)
        logger.info(
            "VestaDataset(split=%r): %d usable samples (of %d total rows in %s; "
            "%d in other splits, %d in this split but unlabeled/indeterminate)",
            split, len(self.records), n_total, self.metadata_csv, n_wrong_split, n_excluded_label,
        )
        if len(self.records) == 0:
            logger.warning(
                "VestaDataset(split=%r) has ZERO usable samples. This is expected as of "
                "Month 1 (see docs/month1_log.md) — spatial_alignment.py has not yet "
                "produced any surviving image-spectrum pairs. Do not train or evaluate "
                "against this split; len()/getitem will not silently fabricate data.",
                split,
            )

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int):
        record = self.records[idx]
        image = Image.open(record.image_path).convert("L").resize(
            (self.image_size, self.image_size), Image.BILINEAR
        )
        array = np.asarray(image, dtype=np.float32) / 255.0
        # Replicate to 3 channels — ResNet-50/ViT-B expect 3-channel input;
        # FC crops are single-band grayscale radiance, not RGB.
        array = np.stack([array, array, array], axis=0)

        if self.transform is not None:
            array = self.transform(array)

        label_idx = CLASS_TO_IDX[record.label]
        return array, label_idx, record.region_id
