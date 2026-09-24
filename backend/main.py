"""
FastAPI backend: /health and /predict.

Month 2 engineering pipeline update: this now loads a real trained
checkpoint and returns real inference — but as of this branch, the ONLY
trained checkpoint(s) available were trained on a SYNTHETIC label set
(datasets/metadata/sample_metadata_SYNTHETIC.csv, see
scripts/generate_synthetic_labels.py and docs/engineering_status.md), not
real Vesta compositional labels. Real compositional labels do not exist
yet on this branch (see month1-data-pipeline's own investigation, in
progress in parallel). So: the prediction, confidence, and heatmap
returned below are all REAL (real forward pass, real gradients, real
model weights) — the training LABELS behind that model are synthetic.
This distinction is documented at every layer (checkpoint filename,
model-type env var default, this docstring, docs/engineering_status.md)
so it can never be read as a real Vesta composition result.

If no checkpoint is configured/found at all, this still returns a clear
503 rather than a fabricated result — that fallback path predates this
change and is unmodified.

Supports two model types (ASTROMINE_MODEL_TYPE env var, 'resnet50' or
'vit_b'): resnet50 uses real Grad-CAM (ml/explainability/gradcam.py);
vit_b uses real attention rollout (ml/explainability/attention_viz.py,
whose forward-hook wiring was implemented this branch — see that
module's docstring). Every real prediction response also carries a fixed
disclaimer, per the project's scientific integrity rules — a prediction
from this endpoint is never presented as a substitute for real
spectroscopy, synthetic-label caveat or not.
"""

from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

from ml.data.dataset import CLASSES
from ml.explainability.attention_viz import vit_attention_rollout
from ml.explainability.gradcam import generate_gradcam
from ml.models import cnn_resnet, vit_model

logger = logging.getLogger("backend")

DISCLAIMER = (
    "This prediction is a preliminary, automated estimate from an "
    "explainable deep learning model trained on a small, exploratory "
    "sample of Dawn mission data. It is NOT a substitute for laboratory "
    "or spectroscopic analysis, and should not be relied on for any "
    "scientific, operational, or financial decision. As of this build, "
    "the model was trained on a SYNTHETIC (not real) label set for "
    "pipeline validation only — see docs/engineering_status.md."
)

# Default model type set to whichever of resnet50/vit_b scored higher on
# the SYNTHETIC validation split (see docs/engineering_status.md for the
# real numbers this was based on) — "best" here is a pipeline-mechanics
# choice, not a claim about which architecture would perform better on
# real compositional labels; overridable via env var regardless.
MODEL_TYPE = os.environ.get("ASTROMINE_MODEL_TYPE", "resnet50")
_DEFAULT_CHECKPOINTS = {
    "resnet50": "trained_models/resnet50_best.pt",
    "vit_b": "trained_models/vit_b_best.pt",
}
CHECKPOINT_PATH = Path(os.environ.get("ASTROMINE_CHECKPOINT", _DEFAULT_CHECKPOINTS.get(MODEL_TYPE, _DEFAULT_CHECKPOINTS["resnet50"])))

app = FastAPI(title="AstroMineAI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_model: Optional[torch.nn.Module] = None


def _load_model() -> Optional[torch.nn.Module]:
    global _model
    if _model is not None:
        return _model
    if not CHECKPOINT_PATH.exists():
        return None
    builder = vit_model if MODEL_TYPE == "vit_b" else cnn_resnet
    model = builder.build_model(num_classes=len(CLASSES), pretrained=False)
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu"))
    model.eval()
    _model = model
    return _model


def _heatmap_to_png_base64(heatmap: np.ndarray, size: tuple[int, int] = (224, 224)) -> str:
    """heatmap: 2D array in [0, 1], any shape (Grad-CAM is already 224x224;
    attention rollout is 14x14 and needs upsampling) -- resized to `size`
    with PIL so both explainability paths return a consistently-sized PNG."""
    img = Image.fromarray((heatmap * 255).astype(np.uint8))
    if img.size != size:
        img = img.resize(size, Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


class PredictResponse(BaseModel):
    prediction: str
    confidence: float
    heatmap_png_base64: str
    disclaimer: str = DISCLAIMER


@app.get("/health")
def health() -> dict:
    model = _load_model()
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "model_type": MODEL_TYPE,
        "checkpoint_path": str(CHECKPOINT_PATH),
        "checkpoint_trained_on": "SYNTHETIC labels (pipeline validation only, not real Vesta composition) — see docs/engineering_status.md",
    }


@app.post("/predict", response_model=PredictResponse)
async def predict(file: UploadFile = File(...)) -> PredictResponse:
    model = _load_model()
    if model is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"No trained model checkpoint found at {CHECKPOINT_PATH} (model_type={MODEL_TYPE!r}). "
                f"Run ml/models/train.py (see docs/engineering_status.md) to produce one -- as of "
                f"this branch, only a SYNTHETIC-label checkpoint has ever been trained here; real "
                f"compositional labels do not exist yet (see month1-data-pipeline). This is reported "
                f"honestly rather than returning a fabricated result."
            ),
        )

    raw = await file.read()
    image = Image.open(io.BytesIO(raw)).convert("L").resize((224, 224), Image.BILINEAR)
    array = np.asarray(image, dtype=np.float32) / 255.0
    tensor = torch.from_numpy(np.stack([array, array, array], axis=0)).unsqueeze(0).float()

    with torch.no_grad():
        logits = model(tensor)
        probs = F.softmax(logits, dim=1)
        confidence, pred_idx = probs.max(dim=1)

    if MODEL_TYPE == "vit_b":
        heatmap = vit_attention_rollout(model, tensor)
    else:
        heatmap = generate_gradcam(model, model.layer4, tensor, target_class=int(pred_idx.item()))
    heatmap_b64 = _heatmap_to_png_base64(heatmap)

    return PredictResponse(
        prediction=CLASSES[int(pred_idx.item())],
        confidence=float(confidence.item()),
        heatmap_png_base64=heatmap_b64,
    )
