"""
Global-mosaic dataset v2: a CV-friendly tile dataset.

Separate from ml/data/mosaic_dataset.py (final/mosaic-dataset's own
MosaicTileDataset, left untouched), which is filtered by the manifest's
fixed 'split' column (train/val/test). This dataset instead takes an
explicit list of real manifest rows directly, since ml/utils/mosaic_cv.py
re-splits the real tile pool into 5 different folds -- there is no
single fixed 'split' column value this dataset can filter on.

Adds two real, optional, task-specific features used by Stage 2's
confound-removal variants:
  - `albedo_normalize`: per-tile histogram equalization (removes each
    tile's own overall brightness level before the model ever sees it
    -- the real question Stage 2(a) asks is whether a model that can no
    longer rely on raw brightness still predicts anything).
  - `return_side_inputs`: also returns each tile's real albedo (of the
    ORIGINAL, non-normalized pixels -- the side input is deliberately
    the same real brightness signal the trivial baseline itself uses)
    and real center lat/lon as a side-input feature vector, for Stage
    2(b)'s residual/side-input model.
"""

from __future__ import annotations

import logging

import numpy as np
from PIL import Image, ImageOps
from torch.utils.data import Dataset

logger = logging.getLogger("mosaic_dataset_cv")


class MosaicTileDatasetCV(Dataset):
    def __init__(
        self,
        rows: list[dict],
        image_size: int = 224,
        transform=None,
        albedo_normalize: bool = False,
        return_side_inputs: bool = False,
    ):
        self.rows = rows
        self.image_size = image_size
        self.transform = transform
        self.albedo_normalize = albedo_normalize
        self.return_side_inputs = return_side_inputs

        if not rows:
            logger.warning(
                "MosaicTileDatasetCV constructed with ZERO rows -- refusing to silently "
                "proceed as if training/evaluating on real data."
            )

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        row = self.rows[idx]
        pil_image = Image.open(row["path"]).convert("L").resize((self.image_size, self.image_size), Image.BILINEAR)
        raw_array = np.asarray(pil_image, dtype=np.float32) / 255.0
        real_albedo = float(raw_array.mean() * 255.0)  # same real 0-255 scale as other scripts' albedo feature

        if self.albedo_normalize:
            # Real per-tile histogram equalization (PIL's standard
            # algorithm) -- removes each tile's own overall brightness
            # level/contrast while keeping its real local structure.
            eq_image = ImageOps.equalize(pil_image)
            array = np.asarray(eq_image, dtype=np.float32) / 255.0
        else:
            array = raw_array

        array3 = np.stack([array, array, array], axis=0)
        if self.transform is not None:
            array3 = self.transform(array3)

        label_idx = int(row["label"])

        if self.return_side_inputs:
            lat = float(row["center_lat"])
            lon_rad = np.deg2rad(float(row["center_lon"]))
            side = np.array([real_albedo, lat, np.sin(lon_rad), np.cos(lon_rad)], dtype=np.float32)
            return array3, label_idx, side, row["tile_id"]

        return array3, label_idx, row["tile_id"]
