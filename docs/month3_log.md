# Month 3 Progress Log

**Status: not started. Blocked on Month 2 — see `docs/month2_log.md`.**

## Prerequisites

- [ ] Month 2's 3-way model comparison complete, with honestly-reported
      results (including if some/all arms underperform given a small,
      exploratory N).
- [ ] Grad-CAM and attention-rollout explanations available for every
      test-set prediction from every model.

## Month 3 scope (once unblocked)

1. Serve the best-performing (or, if none clearly wins given the sample
   size, the most defensible/best-calibrated) model via `backend/main.py`
   — point `ASTROMINE_CHECKPOINT` at the trained checkpoint.
2. `/predict` end-to-end test via the `frontend/` upload page: upload a
   held-out FC crop, confirm the returned prediction, confidence, and
   Grad-CAM heatmap are sane and the disclaimer is present.
3. Write up final results: per-class accuracy, calibration, example
   explanations (Grad-CAM + attention rollout) for both a correct and an
   incorrect prediction per class, and an honest discussion of
   limitations (sample size, class balance, geometry approximations
   carried over from Month 1 — see `docs/month1_log.md`'s noted
   approximations: equirectangular-box IoU, linear-footprint pixel
   mapping for crops, unvalidated size-ratio penalty).
4. Docker Compose smoke test: `docker-compose up`, confirm `backend` and
   `frontend` both start and the frontend can reach `/predict` through
   the dev proxy / compose network.
5. Final honest project write-up: does the explainable-AI framework
   proposed actually produce trustworthy, well-calibrated compositional
   estimates at the sample size Month 1 was able to deliver, or does the
   write-up need to frame this as a proof-of-concept pipeline validated
   on a small N, with a clear path to scaling up the labeled sample
   (repeating Month 1's acquisition against more HAMO/LAMO time windows)
   rather than a fully validated model? Answer honestly, per
   `docs/scientific_integrity_checklist.md`.
