"""
FastAPI backend: /health and /predict.

/predict is honest about the current state of the project: as of Month 1,
there is no trained model (0 surviving labeled samples — see
docs/month1_log.md), so it does not fabricate a prediction. If no
checkpoint is configured/found, it returns a clear 503 rather than a
plausible-looking but meaningless result. Every real prediction response
also carries a fixed disclaimer, per the project's scientific integrity
rules — a prediction from this endpoint is never presented as a substitute
for real spectroscopy.
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
import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

from ml.data.dataset import CLASSES
from ml.explainability.gradcam import generate_gradcam
from ml.models import cnn_resnet

logger = logging.getLogger("backend")

DISCLAIMER = (
    "This prediction is a preliminary, automated estimate from an "
    "explainable deep learning model trained on a small, exploratory "
    "sample of Dawn mission data. It is NOT a substitute for laboratory "
    "or spectroscopic analysis, and should not be relied on for any "
    "scientific, operational, or financial decision."
)

CHECKPOINT_PATH = Path(os.environ.get("ASTROMINE_CHECKPOINT", "trained_models/resnet50_best.pt"))

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
    model = cnn_resnet.build_model(num_classes=len(CLASSES), pretrained=False)
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu"))
    model.eval()
    _model = model
    return _model


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
        "checkpoint_path": str(CHECKPOINT_PATH),
    }


@app.post("/predict", response_model=PredictResponse)
async def predict(file: UploadFile = File(...)) -> PredictResponse:
    model = _load_model()
    if model is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"No trained model checkpoint found at {CHECKPOINT_PATH}. As of Month 1, "
                f"this project has zero spatially-verified, labeled training samples (see "
                f"docs/month1_log.md) — no model has been trained yet, so this endpoint "
                f"cannot return a real prediction. This is reported honestly rather than "
                f"returning a fabricated result."
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

    heatmap = generate_gradcam(model, model.layer4, tensor, target_class=int(pred_idx.item()))
    heatmap_img = Image.fromarray((heatmap * 255).astype(np.uint8))
    buf = io.BytesIO()
    heatmap_img.save(buf, format="PNG")
    heatmap_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return PredictResponse(
        prediction=CLASSES[int(pred_idx.item())],
        confidence=float(confidence.item()),
        heatmap_png_base64=heatmap_b64,
    )
