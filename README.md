# AstroMineAI

An Explainable Deep Learning Framework for Probabilistic Asteroid Surface
Composition Estimation from Remotely Sensed Imagery (SRM UROP project,
Akshat Jha + Ayushman Mayank).

Scope: Vesta only, using Dawn mission (Framing Camera + VIR) data. Builds
and compares a classical ML baseline, ResNet-50, and ViT-B on a
spatially-verified image-to-composition pipeline, with Grad-CAM +
attention-rollout explainability on every prediction.

**Non-negotiable scientific integrity rules** — see
[`docs/scientific_integrity_checklist.md`](docs/scientific_integrity_checklist.md):
no visual-to-mineral label heuristics (labels come from real VIR spectral
absorption features only); every sample carries full provenance metadata;
train/val/test splits are region-based, never random; weak or negative
results are reported honestly.

## Status: project closed out — negative result on the compositional-signal question

**Full writeup: [`docs/FINAL_REPORT.md`](docs/FINAL_REPORT.md).**

The data-science track (16 iterations, `docs/month1_log.md`) built a real
acquisition → spatial-alignment → band-center-extraction pipeline against
the live PDS Small Bodies Node archive, scaled it from 1 real
spatially-verified image-spectrum pair to **2,649 real aligned crops /
312 unique real VIR spectra / 141 paired observations** across both HAMO
and LAMO mission phases, found and fixed four real bugs along the way
(acquisition source, an FC/VIR longitude-convention bug, a band-center
fitting instability, and a recurring manifest-deduplication issue), and
used the final, largest, most diversified real sample specifically to
test whether the pipeline's observed Band II spectral clustering reflects
genuine Vesta composition.

**It does not, within what this project could acquire and test.** The
clustering is explained by acquisition-session timing (84.6%/91.9%
correlation across the two mission phases, replicated almost exactly at
a ~5-6x larger sample than the first check) and by the band-center
method's own per-sample fit confidence (p = 2.6×10⁻⁷ and p = 8.4×10⁻⁵,
independently in each phase) — both at real statistical power, not a
small-sample artifact. This is reported as a final, not provisional,
result (see `docs/month1_log.md`'s Slice 16 for the full real numbers and
the pre-agreed stopping rule it was checked against).

In parallel, a complete training → explainability → backend → frontend →
Docker engineering pipeline was built and verified end-to-end (real
training runs, a real headless-browser check of the deployed UI, a real
`docker compose up` of both containers) on a **clearly-marked synthetic
label set** (`docs/engineering_status.md`), so the system is mechanically
ready to be pointed at real labels the moment a future effort produces
them by a method not subject to the confounds found here.

## Layout

- `ml/data/` — PDS3 acquisition (`pds_acquisition.py`), spatial alignment
  (`spatial_alignment.py`), VIR-only compositional labeling
  (`spectral_labeling.py`, including the fixed `compute_band_center_v2()`),
  and the PyTorch dataset (`dataset.py`).
- `ml/utils/` — shared `SampleMetadata` schema + validation
  (`metadata_schema.py`) and region-based splitting (`splits.py`).
- `ml/models/` — baseline (scikit-learn), ResNet-50, ViT-B, training
  (`train.py`) and evaluation (`evaluate.py`).
- `ml/explainability/` — Grad-CAM (`gradcam.py`) and attention rollout
  (`attention_viz.py`, including the real hook-wiring fix) — both real,
  both verified.
- `backend/` — FastAPI app (`main.py`: `/health`, `/predict`), loads
  either trained model type and routes to the matching explainability
  method.
- `frontend/` — Vite + React + TypeScript upload/predict page
  (`src/App.tsx`).
- `docker/`, `docker-compose.yml` — containerized backend + frontend
  (verified working end-to-end, see `docs/engineering_status.md`).
- `configs/config.yaml` — verified PDS source URLs/volume IDs, real
  mission-phase date windows, model/training config.
- `scripts/` — the real analysis/audit scripts behind every slice's
  findings (`audit_band_separability*.py`, `recheck_confound_*.py`,
  `generate_synthetic_labels.py`, `generate_explainability_samples.py`,
  `screenshot_frontend_predict.py`) plus earlier Month-1 utilities
  (`data_audit.py`, `finalize_month1_labels.py`).
- `docs/` — `FINAL_REPORT.md` (read this first), the month-by-month logs
  (`month1_log.md` is the full real narrative; `month2_log.md`/
  `month3_log.md` record the originally-planned, never-reached scope),
  `engineering_status.md` (real vs. synthetic breakdown for the
  engineering pipeline), the handoff session log
  (`handoff/STATUS.md`), and the integrity checklist.
- `tests/` — pytest suite: `SampleMetadata.validate()` rules, the real
  FC/VIR longitude-convention regression test, and
  `compute_band_center_v2()`'s stability/correctness regression tests.

## How to reproduce the real data-science result

```bash
pip install -r requirements.txt

# Re-run acquisition against the real, verified mission-phase windows
# already in configs/config.yaml (hamo_cycle1, hamo_cycle3, hamo_cycle6,
# lamo_cycle4, lamo_window2) — add --limit N to smoke-test first.
python -m ml.data.pds_acquisition --instrument both --phase hamo_cycle1 -v

# Real spatial alignment (unmodified throughout Slices 10-16)
python -m ml.data.spatial_alignment -v

# Reproduce the confound-investigation numbers in docs/month1_log.md
python scripts/audit_band_separability.py          # Slice 10 (old method)
python scripts/audit_band_separability_v2.py        # Slice 13 (v2 method)
python scripts/recheck_confound_v2.py               # Slice 14
python scripts/recheck_confound_by_phase.py          # Slice 15
python scripts/recheck_confound_slice16.py           # Slice 16 (final)

# Tests
pytest tests/ -q   # 39/39 as of final/closeout
```

## How to run the engineering demo (SYNTHETIC labels — not a Vesta result)

```bash
# Generate the synthetic label set + splits (never touches the real,
# unlabeled sample_metadata.csv)
python scripts/generate_synthetic_labels.py -v

# Train all three arms on it
python -m ml.models.train --model baseline_logreg --metadata-csv datasets/metadata/sample_metadata_SYNTHETIC.csv -v
python -m ml.models.train --model baseline_rf --metadata-csv datasets/metadata/sample_metadata_SYNTHETIC.csv
python -m ml.models.train --model resnet50 --metadata-csv datasets/metadata/sample_metadata_SYNTHETIC.csv --epochs 2 --checkpoint-out trained_models/resnet50_best.pt
python -m ml.models.train --model vit_b --metadata-csv datasets/metadata/sample_metadata_SYNTHETIC.csv --epochs 2 --checkpoint-out trained_models/vit_b_best.pt

# Real explainability samples (Grad-CAM + attention rollout) against the trained checkpoints
python scripts/generate_explainability_samples.py

# Full stack via Docker (verified working end-to-end — see docs/engineering_status.md)
cp .env.example .env && echo "ASTROMINE_MODEL_TYPE=resnet50" >> .env
docker compose up -d
curl -X POST http://localhost:8000/predict -F "file=@datasets/processed/<any real crop>.png"
# frontend: http://localhost:5173
```

**Read `docs/FINAL_REPORT.md` for the full writeup — abstract, methods,
every real number behind the negative result, the engineering system
with its real/synthetic boundary stated plainly, limitations, and the
two concrete future-work routes if compositional labeling is ever
pursued further.**
