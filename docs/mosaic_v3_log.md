# Global-mosaic dataset v3: spatial-prior model + terrane-held-out robustness check

Append-only working log for `final/mosaic-v3` (branched off
`final/mosaic-v2`). Does not modify `docs/month1_log.md`,
`datasets/metadata/sample_metadata.csv`, `ml/data/spatial_alignment.py`,
`ml/utils/splits.py`, the committed Band I tertile thresholds, or any
committed Stage 0-5 result in `docs/mosaic_experiment_log.md` /
`docs/mosaic_v2_log.md`. Labels/thresholds stay exactly as committed
(3-class Band I center tertiles).

**What every model in this log measures, stated once, plainly, up
front: a spatial-prior model predicts a tile's real VIR Band I class
from its real tile-center LOCATION (and, for some candidates, its real
mean FC albedo). None of them is a composition-from-image model, and
none can classify an unlocated image** — see
`ml/utils/mosaic_spatial_models.py`'s own docstring.

**Primary metric**: the identical real 5-fold region-block CV as
`final/mosaic-v2` (same `block_size_deg=20.0`,
`tile_size_deg=224/74.1778`, `n_folds=5`, `seed=42`) — balanced accuracy
and macro-F1, mean ± std across the 5 outer test folds. Tuning (where a
candidate has real hyperparameters) uses only each fold's own inner val
split. The old, fixed 222-tile test set from `final/mosaic-dataset`
stays untouched.

**Reference numbers, quoted next to every result below, per this
task's rule**:

| reference | balanced accuracy (mean ± std) |
|---|---|
| Location-only random forest (lat/lon, no albedo) | 0.7215 ± 0.0961 |
| Albedo + lat/lon random forest (the v1/v2 trivial baseline) | 0.7783 ± 0.0659 |
| Best deep model (residual ResNet-50 + class-weighted, `final/mosaic-v2`) | 0.5637 ± 0.0403 |

## Stage 1: stacked spatial-prior model

### Tabular candidates (`scripts/mosaic_spatial_prior.py`)

Four real candidates, all evaluated under the identical 5-fold CV:
random forest and gradient boosting on `[albedo, lat, sin(lon),
cos(lon)]` (fixed hyperparameters, same convention as every trivial
baseline in this project); a real great-circle-distance k-NN on
`(lat, lon)` only (no albedo, per this task's own spec), k tuned per
fold on that fold's inner val split; a real Gaussian-kernel great-
circle smoother (lat/lon only), bandwidth tuned per fold on inner val —
this task's own sanctioned alternative to a full Gaussian Process
classifier.

| model | balanced accuracy (mean ± std) | macro-F1 (mean ± std) | per-fold hyperparameter |
|---|---|---|---|
| Random forest (albedo+lat/lon) | 0.7783 ± 0.0659 | 0.7815 ± 0.0678 | — |
| Gradient boosting (albedo+lat/lon) | 0.7814 ± 0.0488 | 0.7833 ± 0.0466 | — |
| **k-NN (lat/lon only, tuned k)** | **0.7971 ± 0.0600** | **0.8045 ± 0.0685** | k=[15,10,5,5,15] |
| Kernel smoother (lat/lon only, tuned bandwidth) | 0.7834 ± 0.0496 | 0.7822 ± 0.0566 | bw(deg)=[10,5,5,5,5] |

Per-fold balanced accuracy: fold 0 `[0.8198, 0.7669, 0.8427, 0.7521]`,
fold 1 `[0.7698, 0.7872, 0.7975, 0.8189]`, fold 2 `[0.6856, 0.7405,
0.6849, 0.7209]`, fold 3 `[0.8773, 0.8725, 0.8542, 0.8596]`, fold 4
`[0.7390, 0.7400, 0.8059, 0.7655]` (order: random forest, gradient
boosting, k-NN, kernel smoother).

**Real, interesting finding**: the best tabular candidate is **k-NN on
location alone, with no albedo at all** (0.7971 ± 0.0600) — it beats
the full-feature (albedo+lat/lon) random forest (0.7783 ± 0.0659) by
+0.0188 points, and beats gradient boosting and the kernel smoother too,
despite using strictly less information (no brightness feature) than
three of the other four candidates. This is consistent with Stage 0's
own finding in `final/mosaic-v2` that location carries most of the real
signal here: a model that spends its full capacity on location alone,
tuned per fold, edges out models that also have to weigh a comparatively
weak albedo feature. **Best tabular (spatial-prior) model: k-NN,
0.7971 ± 0.0600 balanced accuracy.**

### Stacking: out-of-fold CNN probabilities added to the best stacking-compatible tabular model

**Correction, caught by a smoke test before this was relied on**: an
earlier version of this section said stacking used k-NN (the overall-
best tabular candidate). That was wrong — the driver script's stacking
step only naturally extends to feature-vector models (random forest /
gradient boosting), since k-NN and the kernel smoother are defined
directly on real great-circle distance over `(lat, lon)` with no
natural way to fold in extra probability-vector dimensions. The code's
`if/else` branch actually always fell through to gradient boosting
whenever the overall-best candidate wasn't literally `"random_forest"`
— which is what ran, but the printed label claimed it stacked onto
k-NN, which it did not. Fixed: the script now explicitly selects the
best of `{random_forest, gradient_boosting}` for stacking
(**gradient boosting, 0.7814 ± 0.0488**, which also happens to be the
real best of those two here) and labels it correctly. The numbers below
were already computed using gradient boosting, so they are unchanged —
only the earlier mislabeling is corrected here.

Real residual ResNet-50 + class-weighted CNN (the exact real recipe
`final/mosaic-v2`'s Stage 3 found to win), trained on each fold's TRAIN
rows only — its probabilities on VAL and TEST rows are genuinely
out-of-fold relative to that CNN's own training, and no outer-test-fold
information ever reaches any model's fit. Because only VAL has honest
out-of-fold CNN probabilities, both the stacked model and a size-
matched tabular-only baseline (both gradient boosting) are fit on VAL
rows only (disclosed explicitly — this is a smaller, matched training
set for both arms, so the comparison isolates the real effect of adding
CNN features, not just a smaller training set):

| fold | n_test | tabular-only (val-only training) | stacked (val-only + CNN probs) |
|---|---|---|---|
| 0 | 292 | 0.6810 | 0.6540 |
| 1 | 307 | 0.5935 | 0.6763 |
| 2 | 304 | 0.5459 | 0.5673 |
| 3 | 295 | 0.7424 | 0.7855 |
| 4 | 296 | 0.4848 | 0.5429 |
| **mean ± std** | | 0.6095 ± 0.0923 | **0.6452 ± 0.0863** |

Delta from adding CNN features: **+0.0357** balanced-accuracy points,
**+0.39 std** of the tabular-only-matched CV spread.

**STACKING VERDICT, per this task's own rule (only counts as an
improvement if it exceeds 1 std): no gain from image features.** The
CNN's out-of-fold probabilities nudge 4 of 5 folds in the right
direction, but the gain (+0.39 std) is well short of the 1-std bar this
task sets for calling it real. Stated plainly: adding the CNN's own
predictions on top of real albedo+lat/lon does not reliably improve a
spatial-prior model here, consistent with every other finding in this
branch and `final/mosaic-v2` — the CNN's real, independent contribution
beyond location/albedo remains unconfirmed.
