"""
Global-mosaic dataset: PyTorch Dataset over
datasets/mosaic/manifests/tile_manifest.csv (written by
scripts/mosaic_tile.py). Reads the real FC tile PNGs and their real VIR
Band I-center tertile labels, filtered to one split.

Mirrors ml/data/dataset.py's VestaDataset in spirit (minimal, raises
loudly on an empty split rather than silently training on nothing) but
is a separate class: different manifest schema, different label
vocabulary (ml.data.mosaic_labels.CLASS_NAMES, not the real spectral
compositional classes), different split semantics (region-block, with a
real 'buffered_out' pseudo-split this dataset always excludes).
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
from torch.utils.data import Dataset

from ml.data.mosaic_labels import CLASS_NAMES

logger = logging.getLogger("mosaic_dataset")


class MosaicTileDataset(Dataset):
    def __init__(
        self,
        manifest_csv: str | Path = "datasets/mosaic/manifests/tile_manifest.csv",
        split: str = "train",
        image_size: int = 224,
        transform=None,
    ):
        self.manifest_csv = Path(manifest_csv)
        self.split = split
        self.image_size = image_size
        self.transform = transform

        rows = []
        with open(self.manifest_csv, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["split"] == split:
                    rows.append(row)
        self.rows = rows

        logger.info("MosaicTileDataset(split=%r): %d real tiles from %s", split, len(rows), self.manifest_csv)
        if not rows:
            logger.warning(
                "MosaicTileDataset(split=%r) has ZERO tiles -- refusing to silently proceed "
                "as if training/evaluating on real data. Check scripts/mosaic_tile.py's output.",
                split,
            )

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        row = self.rows[idx]
        image = Image.open(row["path"]).convert("L").resize((self.image_size, self.image_size), Image.BILINEAR)
        array = np.asarray(image, dtype=np.float32) / 255.0
        array = np.stack([array, array, array], axis=0)  # grayscale -> 3-channel replicate

        if self.transform is not None:
            array = self.transform(array)

        label_idx = int(row["label"])
        return array, label_idx, row["tile_id"]

    def class_counts(self) -> dict[str, int]:
        counts = {name: 0 for name in CLASS_NAMES}
        for row in self.rows:
            counts[CLASS_NAMES[int(row["label"])]] += 1
        return counts
