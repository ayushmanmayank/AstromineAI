"""
Month 2 engineering pipeline: produce a few real Grad-CAM (ResNet-50) and
real attention-rollout (ViT-B) heatmaps against real trained checkpoints,
for docs/engineering_status.md. Uses the SYNTHETIC-label checkpoints
trained by ml/models/train.py on datasets/metadata/sample_metadata_SYNTHETIC.csv
-- every prediction/heatmap here is real (real forward pass, real
gradients/attention), but the label the model was trained toward is
synthetic. Not a claim about real Vesta composition.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.dataset import CLASSES  # noqa: E402
from ml.explainability.attention_viz import vit_attention_rollout  # noqa: E402
from ml.explainability.gradcam import generate_gradcam  # noqa: E402
from ml.models import cnn_resnet, vit_model  # noqa: E402
from ml.utils.metadata_schema import read_metadata_csv  # noqa: E402

OUT_DIR = Path("docs/handoff/artifacts/engineering_explainability_samples")


def _load_image_tensor(image_path: str) -> torch.Tensor:
    image = Image.open(image_path).convert("L").resize((224, 224), Image.BILINEAR)
    array = np.asarray(image, dtype=np.float32) / 255.0
    return torch.from_numpy(np.stack([array, array, array], axis=0)).unsqueeze(0).float()


def _save_heatmap(heatmap: np.ndarray, out_path: Path) -> None:
    if heatmap.shape != (224, 224):
        img = Image.fromarray((heatmap * 255).astype(np.uint8)).resize((224, 224), Image.BILINEAR)
    else:
        img = Image.fromarray((heatmap * 255).astype(np.uint8))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def main() -> int:
    records = read_metadata_csv("datasets/metadata/sample_metadata_SYNTHETIC.csv")
    sample_records = records[:3]

    resnet = cnn_resnet.build_model(num_classes=len(CLASSES), pretrained=False)
    resnet.load_state_dict(torch.load("trained_models/resnet50_best.pt", map_location="cpu"))
    resnet.eval()

    vit = vit_model.build_model(num_classes=len(CLASSES), pretrained=False)
    vit.load_state_dict(torch.load("trained_models/vit_b_best.pt", map_location="cpu"))
    vit.eval()

    summary_lines = []
    for i, rec in enumerate(sample_records):
        tensor = _load_image_tensor(rec.image_path)

        with torch.no_grad():
            r_logits = resnet(tensor)
            r_probs = torch.softmax(r_logits, dim=1)
            r_conf, r_pred = r_probs.max(dim=1)

            v_logits = vit(tensor)
            v_probs = torch.softmax(v_logits, dim=1)
            v_conf, v_pred = v_probs.max(dim=1)

        r_heatmap = generate_gradcam(resnet, resnet.layer4, tensor, target_class=int(r_pred.item()))
        v_heatmap = vit_attention_rollout(vit, tensor)

        _save_heatmap(r_heatmap, OUT_DIR / f"sample{i}_resnet50_gradcam.png")
        _save_heatmap(v_heatmap, OUT_DIR / f"sample{i}_vit_b_attention_rollout.png")

        line = (
            f"sample{i} ({rec.region_id}, synthetic_label={rec.label}): "
            f"resnet50 pred={CLASSES[int(r_pred.item())]} conf={float(r_conf.item()):.3f} | "
            f"vit_b pred={CLASSES[int(v_pred.item())]} conf={float(v_conf.item()):.3f}"
        )
        summary_lines.append(line)
        print(line)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "SUMMARY.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {len(sample_records)*2} heatmap PNGs + SUMMARY.txt to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
