"""
Global-mosaic dataset v2, Stage 5: Grad-CAM on 12 real test tiles,
stratified by true class (4 per class), for this branch's winning real
configuration (residual ResNet-50 + class-weighted loss, 3-class task).

Reuses ml/explainability/gradcam.py's generate_gradcam() unmodified
(same as final/mosaic-dataset's own Stage 5). Only Grad-CAM is run
here, not attention rollout: this branch's winning configuration is
ResNet-50-based (the residual variant), not ViT-B, so attention
rollout does not apply to the model being explained -- stated plainly
rather than run on an architecture that was not the real winner here.

The checkpoint explained (trained_models/mosaic_v2/
residual_resnet50_classweighted_fold0.pt) was trained on fold 0's real
train+val tiles only (scripts/mosaic_train_cv.py --single-fold 0); the
12 real tiles explained here are drawn from fold 0's real, held-out
test tiles (never used in that checkpoint's training), stratified 4 per
class by real label.

ResNetWithSideInputs.forward(x, side) takes two arguments, but
generate_gradcam()/captum's LayerGradCam expect a single-tensor-input
callable -- a small wrapper fixes each tile's own real side-input
vector via closure so the model can be called as model(image_tensor)
only, without modifying gradcam.py or the model class itself.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.mosaic_labels import CLASS_NAMES  # noqa: E402
from ml.explainability.gradcam import generate_gradcam  # noqa: E402
from ml.utils.mosaic_cv import make_cv_folds  # noqa: E402
from scripts.mosaic_train_cv import ResNetWithSideInputs  # noqa: E402

MANIFEST_PATH = "datasets/mosaic/manifests/tile_manifest.csv"
CHECKPOINT_PATH = "trained_models/mosaic_v2/residual_resnet50_classweighted_fold0.pt"
BLOCK_SIZE_DEG = 20.0
TILE_SIZE_DEG = 224 / 74.1778
SEED = 42
FOLD_INDEX = 0
OUT_DIR = Path("docs/handoff/artifacts/mosaic_v2_explainability")


class SideInputWrapper(nn.Module):
    """Fixes one tile's real side-input vector via closure so the
    wrapped model can be called with a single tensor argument, as
    generate_gradcam()/captum's LayerGradCam require."""

    def __init__(self, model: ResNetWithSideInputs, side: torch.Tensor):
        super().__init__()
        self.model = model
        self.side = side

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        side = self.side.expand(x.size(0), -1)
        return self.model(x, side)


def load_all_kept_tiles(manifest_csv: str) -> list[dict]:
    with open(manifest_csv, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh) if row["split"] != "buffered_out"]


def tile_to_tensor_and_side(row: dict) -> tuple[torch.Tensor, torch.Tensor]:
    pil_image = Image.open(row["path"]).convert("L").resize((224, 224), Image.BILINEAR)
    array = np.asarray(pil_image, dtype=np.float32) / 255.0
    real_albedo = float(array.mean() * 255.0)
    lat = float(row["center_lat"])
    lon_rad = np.deg2rad(float(row["center_lon"]))
    side = torch.tensor([[real_albedo, lat, np.sin(lon_rad), np.cos(lon_rad)]], dtype=torch.float32)
    array3 = np.stack([array, array, array], axis=0)
    tensor = torch.from_numpy(array3).unsqueeze(0).float()
    return tensor, side


def main() -> int:
    rows = load_all_kept_tiles(MANIFEST_PATH)
    lats = [float(r["center_lat"]) for r in rows]
    lons = [float(r["center_lon"]) for r in rows]
    folds = make_cv_folds(lats, lons, BLOCK_SIZE_DEG, TILE_SIZE_DEG, n_folds=5, seed=SEED)
    fold = next(f for f in folds if f.fold_index == FOLD_INDEX)
    test_rows = [rows[i] for i in fold.test_idx]
    print(f"Fold {FOLD_INDEX} real test tiles: {len(test_rows)}")

    by_class: dict[int, list[dict]] = {0: [], 1: [], 2: []}
    for r in test_rows:
        by_class[int(r["label"])].append(r)

    selected = []
    for cls in (0, 1, 2):
        pool = by_class[cls]
        if len(pool) < 4:
            print(f"WARNING: only {len(pool)} real test tiles for class {CLASS_NAMES[cls]} "
                  f"in fold {FOLD_INDEX} (need 4) -- using all available, stated honestly.")
        selected.extend(pool[:4])
    print(f"Selected {len(selected)} real tiles, stratified by true class "
          f"({[CLASS_NAMES[int(r['label'])] for r in selected]})")

    model = ResNetWithSideInputs(num_classes=len(CLASS_NAMES), pretrained=False)
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu"))
    model.eval()
    target_layer = model.features[-2]  # real ResNet-50 layer4, last conv block before avgpool

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n=== Grad-CAM on {len(selected)} real, class-stratified test tiles -> {OUT_DIR} ===")
    for i, row in enumerate(selected):
        tensor, side = tile_to_tensor_and_side(row)
        wrapper = SideInputWrapper(model, side)
        with torch.no_grad():
            pred = int(F.softmax(model(tensor, side), dim=1).argmax(dim=1).item())

        heatmap = generate_gradcam(wrapper, target_layer, tensor, target_class=pred)

        base_img = Image.fromarray((tensor[0, 0].numpy() * 255).astype(np.uint8)).convert("L")
        heat_img = Image.fromarray((heatmap * 255).astype(np.uint8)).resize(base_img.size, Image.BILINEAR)
        combined = Image.new("L", (base_img.width * 2 + 10, base_img.height + 20), color=255)
        combined.paste(base_img, (0, 20))
        combined.paste(heat_img, (base_img.width + 10, 20))
        out_path = OUT_DIR / f"{row['tile_id']}_true_{CLASS_NAMES[int(row['label'])]}_pred_{CLASS_NAMES[pred]}.png"
        combined.save(out_path)
        print(f"  [{i+1}/{len(selected)}] {row['tile_id']}: true={CLASS_NAMES[int(row['label'])]} "
              f"pred={CLASS_NAMES[pred]} -> {out_path.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
