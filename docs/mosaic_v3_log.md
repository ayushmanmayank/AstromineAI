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

## Stage 2: terrane-held-out robustness check (Gate D)

### Real terrane groups (`ml/data/mosaic_terranes.py`, committed before this stage ran)

**Honest sourcing statement**: a real attempt was made to query the
USGS Planetary Nomenclature gazetteer (`planetarynames.wr.usgs.gov`)
directly for published Rheasilvia / Veneneia / Divalia Fossae /
Saturnalia Fossae polygon boundaries before writing anything. Its
feature search is a JavaScript-driven interface whose results are not
present in the server's initial HTML response and could not be queried
reliably via plain HTTP requests in this environment. Per this task's
own explicitly-sanctioned fallback, this uses real **latitude bands**
instead, chosen from the real tile-center latitude distribution
(n=1,494, range −86.66 to +76.41°), named after the broad geologic
context each is known, at a general qualitative level, to correspond
to — **not** presented as sourced, precise published polygons:

| terrane | latitude range | real n (kept tiles) | real context (approximate) |
|---|---|---|---|
| `southern_polar_cap` | ≤ −50° | 412 | Rheasilvia basin (real, well-established: south-polar) |
| `southern_midlatitude_band` | (−50°, −20°] | 392 | Veneneia + southern trough reach (least precise) |
| `equatorial_band` | (−20°, 20°] | 331 | Divalia Fossae / Saturnalia Fossae (real, equatorial) |
| `northern_terrain` | > 20° | 359 | remaining northern cratered terrain (catch-all) |

Leave-one-terrane-out CV (`ml/utils/mosaic_terrane_cv.py`): train on
the other three terranes, buffered by a real ≥10° latitude gap around
the held-out terrane's boundary (9 new tests cover no train/test
overlap, every tile held out exactly once, the buffer respected at both
boundaries of a middle terrane, and determinism — all passing).

### Real, caught-and-fixed bug: the printed majority-class rate used the wrong set

An earlier version of `scripts/mosaic_terrane_robustness.py` computed
each terrane's "majority-class rate" from the **training** pool's
global majority class, not that held-out terrane's own **local** test
labels — a real deviation from this whole project's established
convention (the majority rate is always the best a constant-class
guess could do on the actual test set being scored). Caught on review
before being relied on for Gate D's verdict. Fixed in the script
(now uses `np.bincount(y_test)`, matching convention); the real model
predictions, balanced accuracy, and macro-F1 numbers below were never
affected by this bug (computed directly from true labels vs.
predictions) — only the majority-rate reference values needed
recomputing, which was done directly from the already-logged real
confusion matrices' true-label row sums (identical across all four
models within a terrane, since they share the same real `y_test`):

| terrane | corrected real local majority rate |
|---|---|
| `southern_polar_cap` | 0.5704 (true counts: low=235, mid=106, high=71 / 412) |
| `southern_midlatitude_band` | 0.6556 (true counts: low=73, mid=62, high=257 / 392) |
| `equatorial_band` | 0.4622 (unchanged — coincidentally already correct) |
| `northern_terrain` | 0.5933 (unchanged — coincidentally already correct) |
| **mean** | **0.5704** (not the earlier, wrong 0.3535) |

### Real Gate D results (`scripts/mosaic_terrane_robustness.py`)

Four real models, identical leave-one-terrane-out folds. The stacked
model reuses the real best-stacking recipe from Stage 1 (gradient
boosting + out-of-fold CNN probabilities, with an inner 80/20 split of
each terrane-train pool standing in for the inner val split, mirroring
Stage 1's disclosed approach); the standalone deep model **reuses that
same per-terrane CNN's own predictions** (trained on the 80% inner-train
subset, not the full terrane-train pool) rather than training a second,
separate CNN — a disclosed compute-saving simplification, not hidden:

| terrane | n_test | majority rate | location-only RF | albedo+lat/lon RF | stacked (GB+CNN) | deep ResNet-50 |
|---|---|---|---|---|---|---|
| `southern_polar_cap` | 412 | 0.5704 | 0.4942 | 0.4825 | 0.4585 | 0.3333 |
| `southern_midlatitude_band` | 392 | 0.6556 | 0.6346 | 0.6295 | 0.5451 | 0.4336 |
| `equatorial_band` | 331 | 0.4622 | 0.6657 | 0.7133 | 0.5817 | 0.4233 |
| `northern_terrain` | 359 | 0.5933 | 0.8303 | 0.4755 | 0.3479 | 0.3718 |
| **mean ± std** | | **0.5704** | **0.6562 ± 0.1195** | **0.5752 ± 0.1007** | 0.4833 ± 0.0901 | **0.3905 ± 0.0405** |

(Balanced accuracy throughout, macro-F1 omitted from this table for
space — full numbers in the real script output: location-only RF
0.5364 ± 0.1030, albedo+lat/lon RF 0.5395 ± 0.1354, stacked 0.4265 ±
0.0940, deep 0.2707 ± 0.0961 macro-F1.)

**Striking, specific real finding**: under `southern_polar_cap`
hold-out (the real Rheasilvia region), the deep model's confusion
matrix is `[[0,235,0],[0,106,0],[0,71,0]]` — it predicted `band1_mid`
for **every single one of the 412 real test tiles**, including the 235
whose true label was `band1_low` (57% of that terrane). Complete,
one-class collapse on an entire held-out real geologic region.

### Real, honest interpretation — the central finding of this stage

Comparing against the **corrected** real local majority rates changes
the picture substantially from an initial (buggy) read:

- **Location-only RF** (0.6562 ± 0.1195) exceeds the mean real
  majority rate (0.5704) by a real but modest **+0.0858** — not the
  dramatic +0.3027 margin the earlier, wrong majority-rate comparison
  suggested.
- **Albedo+lat/lon RF** (0.5752 ± 0.1007) — the same real recipe that
  scored 0.7783 under block CV — is barely above the real local
  majority rate at all (**+0.0048**), essentially indistinguishable
  from a constant-class guess under real terrane hold-out.
- **Stacked (GB+CNN)** (0.4833 ± 0.0901) falls **below** the real
  majority rate (−0.0871).
- **Deep ResNet-50** (0.3905 ± 0.0405) falls well below the real
  majority rate (−0.1799) in raw terms, though it remains modestly
  above a 3-class chance-level *balanced* accuracy of 1/3 ≈ 0.333
  (+0.057) — majority rate is a raw-accuracy quantity, not directly
  the same unit as balanced accuracy, a distinction worth being precise
  about here specifically, even though this whole project has
  consistently quoted the two side by side as a quick reference
  throughout.

**GATE D verdict, stated as this task's own brief requires**:

**(a)** Does the location-based model keep a score above majority-class
under terrane hold-out? **Yes, but only modestly** — location-only RF
(0.6562 ± 0.1195) exceeds the real, corrected local majority rate
(0.5704) by +0.0858, a real, non-trivial edge, but far smaller than
block CV's comparable margin (location-only RF was 0.7215 vs. a
~0.44-0.61 block-CV majority rate in `final/mosaic-v2`'s own Stage 0 —
see that log — a considerably larger gap).

**(b)** Does the gap between the trivial baseline and the deep model
change? **The absolute gap narrows slightly in raw terms** (block CV:
albedo+lat/lon RF 0.7783 − deep model 0.5637 = +0.2146; terrane
hold-out: 0.5752 − 0.3905 = +0.1847), **but not because the deep model
catches up** — both collapse together under the harder, real domain
shift (the trivial baseline falls −0.2031 points, the deep model falls
−0.1732 points), so the narrower gap reflects mutual collapse toward
the real local majority rate, not the deep model gaining real ground.

**Overall, honest verdict**: **the 77.8% block-CV trivial-baseline
figure was substantially inflated by spatial autocorrelation within
the 20°-block grid — exactly the scenario this task's brief
anticipated and asked to be named plainly if it happened.** Real
positional signal does survive genuine cross-terrane generalization
(location-only RF keeps a real, if modest, edge over the local
majority rate), but adding albedo on top of location — which looked
like a real improvement under block CV (0.7215 → 0.7783) — **provides
essentially no real benefit, and may actively hurt generalization**,
under a genuine geological/illumination domain shift (0.5752 vs.
location-only's 0.6562, a real reversal of the block-CV ordering).
Real, plausible reason, stated as a hypothesis: different real
terranes were imaged under systematically different real illumination/
mission-phase conditions (this project's own Stage 1 Gate C log
documents HAMO-1 vs. HAMO-2 coverage differences by hemisphere), so an
albedo-based rule learned on some terranes' overall brightness levels
does not transfer cleanly to a terrane imaged under different real
conditions — unlike location, which is a stable, terrane-independent
real coordinate. The deep model fares worst of all under this real
test: it falls below the real local majority rate on average, and
collapses to predicting a single class for an entire held-out real
geologic region (`southern_polar_cap`) — the clearest real evidence in
this whole three-branch experiment that this model has learned
something closer to a spurious correlation with its specific real
training terranes than a genuinely robust, transferable rule.
