# Engineering Status — Month 2 (`month2-engineering` branch)

**Read this before touching any number in this document as if it says
something about real Vesta composition. It does not.** Every accuracy,
confidence, and prediction below comes from a model trained on a
**SYNTHETIC** label set (`datasets/metadata/sample_metadata_SYNTHETIC.csv`,
random labels assigned by `scripts/generate_synthetic_labels.py`, seeded
and fully disclosed below) — real compositional labels do not exist yet
on this repo as of this branch. This document's job is to say, as plainly
as every `docs/month1_log.md` entry does, exactly which parts of this
branch are **real engineering** (the pipeline mechanics, the wiring, the
Docker setup — all genuinely built and verified) versus **synthetic
inputs standing in for real science** (the labels, and therefore any
number derived from them).

Branched from `month1-data-pipeline` at commit `dffdde3` (Slice 15).
Track A (the real compositional-signal investigation) continued in
parallel on `month1-data-pipeline` throughout this task — see "Track A
status" at the end.

## What's REAL (pipeline mechanics — this is the actual deliverable)

- **Synthetic dataset generation** (`scripts/generate_synthetic_labels.py`):
  reads the real, unmodified 787-row `sample_metadata.csv` (50 unique real
  VIR spectra, all real FC/VIR-aligned crops from Month 1's pipeline) and
  assigns one synthetic label per unique real spectrum (not per crop) via
  a seeded (`seed=42`) uniform-random draw over the same 3-class
  vocabulary `ml/data/dataset.py` already defines
  (`diogenite_like`/`howardite_like`/`eucrite_like`). Real distribution:
  22/12/16 spectra respectively. Written to
  `datasets/metadata/sample_metadata_SYNTHETIC.csv` — the real
  `sample_metadata.csv` was never opened for writing (verified: its
  `label`/`split` columns are still `unlabeled`/`unassigned` after
  running this). Every `label_source` on the synthetic file starts with
  `"SYNTHETIC_DEMO -- not a real compositional label"` and names the
  exact seed/rule.
- **Splits**: `ml/utils/splits.py`'s `assign_region_based_splits()` run
  **completely unmodified** on the synthetic dataset using this project's
  real `configs/config.yaml` split settings (0.70/0.15/0.15, seed 42, 5°
  bins) — real result: 555/103/129 train/val/test.
- **Training, actually run end-to-end** (`ml/models/train.py`, extended
  with a `--metadata-csv` override flag — default behavior for the real
  dataset is unchanged):
  | model | val accuracy | notes |
  |---|---|---|
  | logistic regression baseline | 29.1% | `ml/models/baseline.py`, real sklearn fit |
  | random forest baseline | 50.5% | same |
  | ResNet-50 (2 epochs) | 40.8% → 57.3% | checkpoint: `trained_models/resnet50_best.pt` |
  | ViT-B (2 epochs) | 38.8% → 38.8% (flat) | checkpoint: `trained_models/vit_b_best.pt` |

  Test-split evaluation (`ml/models/evaluate.py`, also extended with
  `--metadata-csv`): ResNet-50 **56.6%** accuracy / 0.200 ECE; ViT-B
  **37.2%** accuracy / 0.197 ECE (both real numbers, both meaningless as
  composition signal — see caveat below).
- **Grad-CAM** (`ml/explainability/gradcam.py`): already real code before
  this branch: verified again here against the actual trained checkpoint.
- **Attention rollout — the real fix this branch made**
  (`ml/explainability/attention_viz.py`): the math (`attention_rollout()`)
  was already correct, but the hook wiring to capture real per-layer
  attention weights from a timm ViT-B forward pass did not exist. Checked
  the installed timm version (1.0.29) directly rather than assuming: its
  default `fused_attn` path (`F.scaled_dot_product_attention`) never
  materializes/returns the attention matrix, and a plain
  `register_forward_hook` can't see it either (the module only returns
  final output). Fixed by temporarily monkey-patching each
  `block.attn.forward` with a faithful reimplementation of the manual
  (non-fused) path that stashes the softmax weights, restored via
  try/finally so a model is never left mutated. Verified against a real
  ViT-B forward pass: captures exactly 12 real `(1, 12, 197, 197)`
  attention tensors, produces a real 14×14 rollout heatmap, output
  unaffected, forward cleanly restored afterward.
- **3 real sample predictions + heatmaps**
  (`scripts/generate_explainability_samples.py`): both models' real
  Grad-CAM / attention-rollout outputs on 3 real crops, saved to
  `docs/handoff/artifacts/engineering_explainability_samples/` (6 PNGs +
  `SUMMARY.txt`). Honest observation from this run: ViT-B predicted
  `eucrite_like` on all 3 samples at nearly identical confidence (~0.57)
  — consistent with its flat val accuracy across both epochs, and
  reported here as likely mode collapse (predicting one dominant class
  regardless of input) rather than glossed over.
- **Backend** (`backend/main.py`): this file was **already real, working
  inference code before this branch**, not the "501 stub" this task's
  brief assumed — noted here as a real premise mismatch, not silently
  worked around. What changed: it now supports both model types via
  `ASTROMINE_MODEL_TYPE` (`resnet50`/`vit_b`, default `resnet50` — the
  better-performing model **on the synthetic metric only**, per this
  task's own instruction to load "the best-performing... model" while
  being honest that this doesn't mean anything about real composition);
  routes to real Grad-CAM or real attention rollout accordingly; the
  fixed disclaimer field is intact and now also states the
  synthetic-label caveat directly in the API response.
- **Frontend** (`frontend/src/App.tsx`): this is the real upload/predict
  UI — the task's brief named a separate `UploadPredict.tsx` that does
  not exist in this repo; documented here as the second real premise
  mismatch rather than creating a redundant duplicate file at the
  assumed path. Verified working end-to-end via a real headless-browser
  run (Playwright) against the **real running backend**: uploaded a real
  test crop, clicked Predict, confirmed the real prediction, real
  Grad-CAM heatmap, and updated disclaimer actually render in the DOM
  with zero console errors — screenshots at
  `docs/handoff/artifacts/engineering_frontend_before.png` and
  `..._after_predict.png`.
- **Docker — verified by actually running it, not assumed**: the task's
  brief said `docker-compose.yml` and its Dockerfiles were "currently
  missing" — they already existed (third premise mismatch, documented).
  Verifying them (`docker compose build && docker compose up`) surfaced
  **three real bugs**, all fixed and re-verified:
  1. `backend.Dockerfile` installed the default PyPI `torch` wheel, which
     pulled ~1GB+ of unused NVIDIA CUDA/cuDNN dependencies into a
     CPU-only inference container (confirmed live: a 554.6MB `torch`
     wheel followed by a 553.1MB `nvidia_cudnn_cu13` wheel, for a
     container that only ever runs `model.eval()` CPU inference). Fixed
     by installing `torch`/`torchvision` from PyTorch's CPU-only wheel
     index first.
  2. `docker-compose.yml`'s backend service references a `.env` file that
     did not exist — only `.env.example` did, with its own comment
     saying to copy it. That copy step had simply never been performed;
     done now (`ASTROMINE_MODEL_TYPE=resnet50` added alongside the
     existing `ASTROMINE_CHECKPOINT`).
  3. **The real, load-bearing one**: the production frontend build
     (`vite build` + `serve -s dist`) has no reverse proxy — unlike
     `npm run dev`'s `vite.config.ts` proxy, which is a dev-server-only
     feature. A relative `fetch("/predict")` from the built app silently
     hit the frontend container's own static server and got back its
     `index.html` shell instead of the backend's JSON — a real bug this
     task's instruction to "verify this actually works, don't just write
     the compose file and assume" was specifically written to catch, and
     did. Fixed with a build-time `VITE_API_BASE_URL` (new
     `frontend/src/vite-env.d.ts` for its TypeScript typing, wired
     through `docker-compose.yml`'s build `args` → `frontend.Dockerfile`
     → `App.tsx`), pointed at the backend's real published host URL.
     Re-verified with a real Playwright browser run against the actual
     rebuilt container (not a leftover local dev-server process — see
     the sidebar below): real rendered prediction, heatmap, disclaimer,
     zero console errors.

  Final state, confirmed working: `docker compose build` succeeds for
  both services (`astromineai-backend:latest` 503MB,
  `astromineai-frontend:latest` 314MB); `docker compose up -d` starts
  both containers; the deployed stack serves real predictions end to
  end.

  *Sidebar, for whoever reruns this*: while manually verifying this, a
  local `npm run dev` process left a stray Node child listening on
  `[::1]:5173` after its wrapping shell was killed (npm doesn't forward
  `SIGTERM` to the process it spawns) — this shadowed the real Docker
  container on `localhost` (which resolves to `::1` first) and produced
  a false-positive "it works" the first time around. Not a defect in any
  delivered file — a testing-process gotcha, noted so it isn't
  rediscovered the hard way. `netstat -ano | grep 5173` plus killing by
  PID (not by port-owning shell) is what caught and fixed it.

## What's SYNTHETIC (do not read as science)

- Every `label` in `sample_metadata_SYNTHETIC.csv`.
- Every accuracy/confidence/ECE number in this document and in
  `trained_models/*.pt`'s training logs.
- Every prediction shown in the screenshots/heatmap samples referenced
  above (`diogenite_like (44.2%)`, etc.) — a real number computed by a
  real model, trained toward a fake target.
- "ResNet-50 beat ViT-B" (57.3% vs 38.8%) is a real comparison of
  **which architecture fit random noise better in 2 epochs**, not
  evidence either architecture is better suited to real Vesta spectral
  classification.

## Track A status (as of this branch)

Track A (Slice 16 on `month1-data-pipeline`: a bounded, final acquisition
attempt to find real compositional signal, with an explicit stopping
rule) was running in parallel throughout this task and **had not
concluded** by the time this document was written — still mid-acquisition
(HAMO cycle 3 of 3 new windows), no real labels produced yet. If/when it
finishes, this branch's synthetic dataset and checkpoints are ready to be
swapped out: re-run `scripts/generate_synthetic_labels.py`'s real
equivalent (a real labeling script, not yet written, once Slice 16 lands)
against whatever `sample_metadata.csv` Track A produces, then re-run
`ml/models/train.py` unchanged. No merge was attempted between the two
branches, per this task's explicit instruction.

## How to reproduce every number above

```bash
python scripts/generate_synthetic_labels.py -v
python -m ml.models.train --model baseline_logreg --metadata-csv datasets/metadata/sample_metadata_SYNTHETIC.csv -v
python -m ml.models.train --model baseline_rf --metadata-csv datasets/metadata/sample_metadata_SYNTHETIC.csv
python -m ml.models.train --model resnet50 --metadata-csv datasets/metadata/sample_metadata_SYNTHETIC.csv --epochs 2 --checkpoint-out trained_models/resnet50_best.pt
python -m ml.models.train --model vit_b --metadata-csv datasets/metadata/sample_metadata_SYNTHETIC.csv --epochs 2 --checkpoint-out trained_models/vit_b_best.pt
python -m ml.models.evaluate --model resnet50 --checkpoint trained_models/resnet50_best.pt --metadata-csv datasets/metadata/sample_metadata_SYNTHETIC.csv --split test
python -m ml.models.evaluate --model vit_b --checkpoint trained_models/vit_b_best.pt --metadata-csv datasets/metadata/sample_metadata_SYNTHETIC.csv --split test
python scripts/generate_explainability_samples.py
cp .env.example .env && echo "ASTROMINE_MODEL_TYPE=resnet50" >> .env
docker compose build && docker compose up -d
curl -X POST http://localhost:8000/predict -F "file=@datasets/processed/<any real crop>.png"
```
