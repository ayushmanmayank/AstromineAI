# AstroMineAI

An Explainable Deep Learning Framework for Probabilistic Asteroid Surface
Composition Estimation from Remotely Sensed Imagery (SRM UROP project,
Akshat Jha + Ayushman Mayank).

Scope: Vesta only, using Dawn mission (Framing Camera + VIR) data. Compares
a classical ML baseline, ResNet-50, and ViT-B on a spatially-verified
image-to-composition pipeline, with Grad-CAM + attention-rollout
explainability on every prediction.

**Non-negotiable scientific integrity rules** — see
[`docs/scientific_integrity_checklist.md`](docs/scientific_integrity_checklist.md):
no visual-to-mineral label heuristics (labels come from real VIR spectral
absorption features only); every sample carries full provenance metadata;
train/val/test splits are region-based, never random; weak or negative
results are reported honestly.

## Status

**Month 1: NO-GO for Month 2 as scoped.** The data pipeline is fully built
and tested, but the currently-downloaded sample yields **0** spatially-
verified image-spectrum pairs — see
[`docs/month1_log.md`](docs/month1_log.md) for the full audit, root cause,
and concrete next steps. Do not start Month 2 work
([`docs/month2_log.md`](docs/month2_log.md)) until that's resolved.

## Layout

- `ml/data/` — PDS3 acquisition (`pds_acquisition.py`), spatial alignment
  (`spatial_alignment.py`), VIR-only compositional labeling
  (`spectral_labeling.py`), and the PyTorch dataset (`dataset.py`).
- `ml/utils/` — shared `SampleMetadata` schema + validation
  (`metadata_schema.py`) and region-based splitting (`splits.py`).
- `ml/models/` — baseline (scikit-learn), ResNet-50, ViT-B, training and
  evaluation.
- `ml/explainability/` — Grad-CAM (real) and attention rollout (stub —
  see the module for its TODO).
- `backend/` — FastAPI app (`/health`, `/predict`).
- `frontend/` — Vite + React + TypeScript upload/predict page.
- `docker/`, `docker-compose.yml` — containerized backend + frontend.
- `configs/config.yaml` — verified PDS source URLs, model/training config.
- `docs/` — month-by-month progress logs + the integrity checklist.
- `tests/` — pytest suite (currently: `SampleMetadata.validate()` rules).

## Usage

```bash
pip install -r requirements.txt

# Data pipeline
python -m ml.data.pds_acquisition --limit 10 -v   # smoke test first
python -m ml.data.spatial_alignment -v
python scripts/data_audit.py
python scripts/finalize_month1_labels.py

# Tests
pytest tests/

# Backend (once a model is trained — see docs/month2_log.md)
cp .env.example .env
docker-compose up
```
