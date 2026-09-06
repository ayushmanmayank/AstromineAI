# Month 2 Progress Log

**Status: not started. Blocked on Month 1's go/no-go call — see
`docs/month1_log.md`'s Slice 3/4 close-out: NO-GO, 0 surviving
image-spectrum pairs.** Do not begin Month 2 work until acquisition has
been re-run against a shared HAMO/LAMO time window for both FC and VIR
and `ml/data/spatial_alignment.py` reports a real, non-zero, adequately
distributed sample.

## Prerequisites checklist (must all be true before starting Month 2)

- [ ] `ml/data/pds_acquisition.py` re-run against a mission phase where FC
      frames carry real footprint geometry (`MINIMUM_LATITUDE` etc. not
      `"N/A"`) — e.g. HAMO or LAMO, not approach-phase OpNav frames.
- [ ] FC and VIR products acquired for the **same time window** (same
      phase-dated directory), not independently-sampled index rows.
- [ ] `ml/data/spatial_alignment.py` run against the new sample; real
      confidence-score distribution and surviving-pair count recorded in
      `docs/month1_log.md`.
- [ ] Month 1 data audit (`scripts/data_audit.py`) re-run against the new,
      non-empty `sample_metadata.csv`; sample size and spatial/temporal
      distribution assessed honestly for whether a 3-way comparison is
      supportable, or whether Month 2 needs to be scoped down (fewer
      classes, binary instead of multi-class, or explicitly framed as
      exploratory given N).
- [ ] Labels assigned via `ml/data/spectral_labeling.py` (VIR-only, no
      image-based heuristics) and splits assigned via
      `ml/utils/splits.py`; class balance recorded.

## Month 2 scope (once unblocked)

1. Train and compare all three arms on the real, split dataset:
   - `ml/models/baseline.py` (logistic regression / random forest)
   - `ml/models/cnn_resnet.py` (ResNet-50, via `ml/models/train.py --model resnet50`)
   - `ml/models/vit_model.py` (ViT-B, via `ml/models/train.py --model vit_b`)
2. Evaluate each on the held-out test split via `ml/models/evaluate.py`:
   accuracy + Expected Calibration Error, reported honestly per class,
   not just in aggregate (small-N classes should have their per-class
   numbers shown, not folded into a misleadingly high macro-average).
3. Wire up `ml/explainability/attention_viz.py`'s forward-hook TODO for
   real ViT-B attention rollout (currently a stub — see the module
   docstring for exactly what's missing).
4. Grad-CAM (`ml/explainability/gradcam.py`, already real) + attention
   rollout run on every test-set prediction from every model, saved
   alongside predictions for later review.
5. Honest reporting: if any arm's result is weak, negative, or not
   meaningfully better than chance given the real N, that gets written
   down here plainly — not hidden, not reframed as a stronger result than
   it is (see `docs/scientific_integrity_checklist.md`).
