# AstroMineAI — Final Report

**Project**: An Explainable Deep Learning Framework for Probabilistic
Asteroid Surface Composition Estimation from Remotely Sensed Imagery
(SRM UROP project, Akshat Jha + Ayushman Mayank). Scope: Vesta only,
Dawn mission Framing Camera (FC) + VIR spectrometer data.

**Branches**: `month1-data-pipeline` (data/science track, ends at
`0033a02`) and `month2-engineering` (pipeline/serving track, ends at
`cb161dd`), merged into `final/closeout` for this report.

Every number in this report is copied from a committed log entry
(`docs/month1_log.md`, `docs/handoff/STATUS.md`, `docs/engineering_status.md`)
or a committed artifact — none are recomputed or rounded up for this
document.

---

## Abstract

This project set out to build and validate an explainable deep-learning
pipeline for estimating HED (howardite-eucrite-diogenite) compositional
class from Dawn mission Framing Camera imagery of Vesta, using VIR
spectrometer data as the only source of ground-truth labels. Across 16
data-science iterations ("Slices") on real PDS3 archive data, the
project built a verified acquisition → spatial-alignment → band-center
extraction pipeline, scaled it from 1 to 2,649 real spatially-verified
image-spectrum pairs (312 unique VIR spectra, 141 paired observations
across HAMO and LAMO mission phases), found and fixed four real
implementation bugs along the way, and used the final, largest, most
diversified real sample specifically to test whether the pipeline's
Band II spectral clustering reflects genuine compositional signal. **It
does not, within the limits of what this project could acquire and
test**: the observed clustering is explained by acquisition-session
timing (84.6-91.9% correlation, replicated at two very different sample
sizes) and by the band-center fitting method's own per-sample confidence
(p = 2.6×10⁻⁷ and p = 8.4×10⁻⁵ in the two mission phases independently)
at a statistical power this project's final, deliberately-enlarged
sample was specifically built to reach. In parallel, a complete
training → explainability → backend → frontend → Docker engineering
pipeline was built and verified end-to-end on a clearly-marked synthetic
label set, so the system is mechanically ready to be pointed at real
labels the moment a future effort produces them by a method not subject
to the confounds found here.

## Background and research question

From the project's own stated scope (`README.md`): build an explainable
deep-learning framework comparing a classical ML baseline, ResNet-50, and
ViT-B on a spatially-verified image-to-composition pipeline for Vesta,
with Grad-CAM and attention-rollout explainability on every prediction,
under a non-negotiable scientific-integrity rule set
(`docs/scientific_integrity_checklist.md`): no visual-to-mineral label
heuristics (labels must come from real VIR spectral absorption features,
never from looking at the FC image), full data provenance on every
sample, region-based (never random) splits, and honest reporting of
weak or negative results.

The underlying research question: **can real Dawn FC imagery of Vesta be
mapped to a real HED compositional class (diogenite-like /
howardite-like / eucrite-like), derived from real, independently-measured
VIR Band I / Band II pyroxene absorption features, with enough confidence
to train and explain a deep-learning classifier?** Month 2 and Month 3
were originally scoped (`docs/month2_log.md`, `docs/month3_log.md`) to
train/compare the three model arms and serve the best one, contingent on
Month 1 producing a real, adequately-diverse labeled sample. That
contingency was never met — this report is the final, honest answer to
why not.

## Data and provenance

**Source**: PDS Small Bodies Node, `sbnarchive.psi.edu` (confirmed live
host for both Dawn FC and Dawn VIR Vesta-phase data; the Geosciences and
Imaging PDS nodes were checked and confirmed to **not** host Dawn data —
Slice 1). Every URL was hand-verified to resolve and serve the claimed
data before being written to `configs/config.yaml`.

**Instruments/datasets used**:
- Dawn FC2, calibrated RDR: `DAWN-A-FC2-3-RDR-VESTA-IMAGES-V1.0`, volume
  `DWNVFC2_1B`.
- Dawn VIR, calibrated RDR, both channels: IR
  `DAWN-A-VIR-3-RDR-IR-VESTA-SPECTRA-V1.0` (`DWNVVIR_I1B`), VIS
  `DAWN-A-VIR-3-RDR-VIS-VESTA-SPECTRA-V1.0` (`DWNVVIR_V1B`).

**Mission phases / acquisition windows used** (real, INDEX.TAB-verified
date ranges, `configs/config.yaml`'s `data.mission_phases`):

| window | phase | real date range | role |
|---|---|---|---|
| `hamo_cycle1` | HAMO | 2011-09-29 to 2011-10-05 | original Slice 6-9 acquisition |
| `lamo_cycle4` | LAMO | 2012-01-07 to 2012-01-09 | Slice 11's independent structural test |
| `hamo_cycle3` | HAMO | 2011-10-11 to 2011-10-16 | Slice 16, session-timing diversification |
| `hamo_cycle6` | HAMO | 2011-10-26 to 2011-11-01 | Slice 16, HAMO's real final cycle |
| `lamo_window2` | LAMO | 2012-04-13 to 2012-04-18 | Slice 16, denser LAMO sample |

**Final real counts** (Slice 16, `align_dataset()` unmodified):
**2,649 aligned image-spectrum crops**, resolving to **312 unique real
VIR spectra**, pairing (by shared `SPACECRAFT_CLOCK_START_COUNT`) into
**141 real paired observations: 104 HAMO + 37 LAMO** (30 clocks excluded
as genuinely VIS-only or IR-only, not hidden). This is up from 1 survivor
(Slice 8), to 743/30 (Slice 9), to 787/50 (through Slice 15), to the
final 2,649/312/141.

Every surviving row carries full provenance (mission, both instruments,
both dataset IDs, both product IDs, real start times, real geometry) per
`ml/utils/metadata_schema.py`'s `SampleMetadata.validate()` — enforced,
not just intended.

## Methods

**Spatial alignment** (`ml/data/spatial_alignment.py`): pairs FC images
against VIR spectral cubes by real body-fixed-frame footprint overlap
(IoU) plus time proximity, within a 24-hour window, keeping pairs above
a 0.30 confidence threshold. Two real bugs were found and fixed here
early on (Slices 6-8, prior to this report's six-slice confound
investigation): the original acquisition source lacked real footprint
geometry (approach-phase OpNav data), and an FC/VIR longitude-convention
mismatch inflated FC's true ~18.69° longitude span to ~341.31° before a
regression test caught it. Left completely unmodified throughout Slices
10-16.

**Band-center extraction** (`ml/data/spectral_labeling.py`): Band I
(~0.9-1.0 μm) and Band II (~1.9-2.0 μm) pyroxene absorption centers via
continuum-removed parabola fitting. Slice 12 diagnosed, and Slice 13
fixed, a real instability in the original method
(`compute_band_center()`): under realistic noise, it discretely snapped
between two ~0.2 μm-separated values (spread jumping from 0.00016 μm at
0.1% noise straight to a ~0.21 μm plateau by 0.5% noise), because its
single-global-argmin, narrow 3-point parabola fit could not distinguish
genuinely near-tied competing local minima in the real, somewhat noisy
continuum-removed curve. The fix, `compute_band_center_v2()` (left
alongside the original, unmodified, for comparison): a smooth
(soft-argmin/Boltzmann) depth-weighted centroid across genuine discrete
local minima, which grows its output spread smoothly and monotonically
with noise instead of jumping (0.00896 → 0.15203 μm across 0.1%-5.0%
noise), while still matching the original method to within 1e-6 μm on a
clean, unambiguous synthetic feature.

**Confound checks**: silhouette scores (`sklearn.cluster.KMeans` +
`silhouette_score`, `random_state=42`, k=2/3/4 all reported); real
session grouping by a data-driven gap rule on real `START_TIME` values
(a new session starts when the gap since the previous observation
exceeds 30 minutes — chosen because real within-session gaps are
minutes and between-session gaps are hours, for both HAMO and LAMO, so
no tuning was needed); real geography/illumination angle pulled from
each observation's own `.LBL` (`INCIDENCE_ANGLE`, `EMISSION_ANGLE`,
`PHASE_ANGLE`, `CENTER_LATITUDE`, `CENTER_LONGITUDE`); Fisher exact test
(mission phase × cluster) and Mann-Whitney U test (fit confidence ×
cluster).

## Results: the negative finding

### Slice 10 — the original bimodality and its first confound

15 real paired HAMO observations (from 743 crops / 30 spectra). Band I
center was nearly flat (0.9212-0.9221 μm); Band II was sharply bimodal
(9 near 1.957 μm, 6 near 2.164 μm). Silhouette (old method):

| k | score |
|---|---|
| 2 | 0.9982 |
| 3 | 0.9058 |
| 4 | 0.7234 |

Geography and illumination angle both ruled out as drivers (ranges
overlap substantially between clusters in both). Acquisition time did
not: **14 of 15 observations** split cleanly by which ~1-hour
acquisition window they fell in.

### Slice 11 — an independent structural test (LAMO) and a new hypothesis

8 real paired LAMO observations (from a separate, independent mission
phase). Silhouette: 0.8740 / 0.6175 / 0.5192. LAMO reproduced HAMO's
*exact* two Band II values (~1.957 μm, ~2.164 μm) to ~0.001 μm — a level
of numeric recurrence that raised a third hypothesis neither track had
considered: a band-center-fitting quantization/instability artifact,
not tested further in that slice.

### Slice 12 — the artifact hypothesis, tested and supported

Real IR grid spacing near 2 μm: 0.0090-0.0100 μm. All 6 real spectra
checked shared the same 3-4 near-tied competing local minima. A
perturbation test on one real spectrum showed the old method's output
jump discretely between the two real cluster values under realistic
(0.5-2%) noise, with no change to the input's true composition.
**Verdict: SUPPORTED.**

### Slice 13 — the fix, and what survives it

`compute_band_center_v2()` built, validated (see Methods), and re-run on
the same real data:

| dataset | old method (buggy) | v2 method |
|---|---|---|
| HAMO-only, n=15 | 0.9982 / 0.9058 / 0.7234 | 0.590 / 0.621 / 0.588 |
| LAMO-only, n=8 | 0.8740 / 0.6175 / 0.5192 | 0.607 / 0.669 / 0.468 |
| Combined, n=23 | — | 0.538 / 0.581 / 0.551 |

A substantial drop, not a total collapse. All 23 of 23 real observations
flagged `ambiguous=True` for both bands under the corrected method.

### Slice 14 — does the session confound survive the fix? (and a new one appears)

v2 k=2 clustering on the same 23 observations (cluster sizes 11/12, far
more balanced than the old method's near-discrete splits). Session
match: **19 of 23 (HAMO 12/15 = 80.0%, LAMO 7/8 = 87.5%)** — weaker than
Slice 11's 93.3% but still well above chance. A **new** confound emerged
from combining HAMO+LAMO into one clustering: mission phase correlated
with cluster assignment (Fisher exact odds=14.0, **p = 0.027**) —
undetectable by Slices 10/11's phase-separated analyses. Fit confidence
also correlated with cluster (Mann-Whitney **p = 0.0042**).

### Slice 15 — controlling for mission phase

Re-separated HAMO (n=15) and LAMO (n=8). HAMO's session-match rose to
**13/15 = 86.7%** (closer to the original 93.3% — phase-mixing had
*diluted* the confound, not inflated it). LAMO's confidence-cluster
association was a **perfect rank separation** (the 3-member cluster held
exactly the 3 highest confidence values of all 8 LAMO observations;
Mann-Whitney p = 0.036, the floor value achievable at that sample size).
Verdict: both confounds remain live; n=15/n=8 both too small to be fully
conclusive on their own.

### Slice 16 — the final, bounded, larger-sample test

Two new HAMO cycles (`hamo_cycle3`, `hamo_cycle6`, confirmed different
real session time-of-day patterns than `hamo_cycle1`) and one denser new
LAMO window (`lamo_window2`) acquired specifically to break the
confounds with more, more diverse real data. Real alignment: 2,649
survivors / 312 unique spectra / 141 paired observations (104 HAMO + 37
LAMO).

| phase | n | silhouette k=2/3/4 | session-confound match | confidence Mann-Whitney p |
|---|---|---|---|---|
| HAMO (3 cycles combined) | 104 | 0.528 / 0.540 / 0.474 | **88/104 = 84.6%** (31 real sessions) | **2.6×10⁻⁷** |
| LAMO (2 windows combined) | 37 | 0.517 / 0.435 / 0.473 | **34/37 = 91.9%** (4 real sessions) | **8.4×10⁻⁵** |

Reference check, combined (phase-mixed): Fisher exact odds=26.9,
**p = 1.2×10⁻⁹** (vs. odds=14.0, p=0.027 at n=23 in Slice 14) — the
mission-phase confound scales up, not away.

**Both the session-match rate and the confidence association replicate
almost exactly across a 5-6x increase in sample size**, now at real
statistical power rather than small-sample suggestion. Applying the
pre-agreed stopping rule: structure survives (silhouette 0.43-0.54,
not near zero) but session and confidence both explain most of it, at
high power, in both mission phases independently. **This is the
negative-result branch of the stopping rule, not the positive one.**

### Four real bugs found and fixed across this investigation

1. **Acquisition source** (Slice 6): original pull used approach-phase
   OpNav data with no real footprint geometry; fixed by filtering to
   HAMO/LAMO windows.
2. **FC/VIR longitude convention** (Slice 7): one uniform transform
   (built from VIR-only evidence) inflated FC's true ~18.69° longitude
   span to ~341.31°; fixed with an instrument-aware standardization,
   caught by a regression test written to fail against the pre-fix code
   first.
3. **Band-center fitting instability** (Slices 12-13): the root cause of
   this report's entire confound investigation — see Methods/Results
   above.
4. **Manifest deduplication** (Slices 9, 11, 16): `pds_acquisition.py`'s
   append-only manifest writer duplicates entries across repeated
   acquisition calls; worked around by a data-level dedup each time it
   recurred (not a code fix, to keep that file's scope narrow per every
   slice's explicit protected-file list).

A fifth, cosmetic-only issue was found but deliberately not fixed in
Month 1's scope: `spatial_alignment.py`'s alignment-summary log line has
a format-string argument-count mismatch (prints a nonsensical "N VIR
candidates" using the time-window hour count instead), confirmed to
affect only a human-readable log message, not the real CSV output or any
computed field. See "Future work" for its optional fix on this branch.

## Engineering system — validated on SYNTHETIC labels only

**Every number in this section is a pipeline-mechanics validation, not a
Vesta composition result — the underlying labels are synthetic, as
labelled throughout.**

A full training → explainability → backend → frontend → Docker pipeline
was built on the `month2-engineering` branch (merged here) and run
end-to-end against a synthetic label set: one seeded (`seed=42`),
uniform-random label per unique real spectrum (not per crop; 22/12/16
spectra across the 3-class vocabulary), written to
`datasets/metadata/sample_metadata_SYNTHETIC.csv`
(`scripts/generate_synthetic_labels.py`), with the real,
never-overwritten `sample_metadata.csv` left untouched. Region-based
splits (unmodified `assign_region_based_splits()`): 555/103/129
train/val/test.

**Model comparison table — pipeline validation on synthetic labels, not evidence about Vesta composition:**

| model | val accuracy | test accuracy | test ECE |
|---|---|---|---|
| Logistic regression baseline | 29.1% | — | — |
| Random forest baseline | 50.5% | — | — |
| ResNet-50 (2 epochs) | 40.8% → 57.3% | 56.6% | 0.200 |
| ViT-B (2 epochs) | 38.8% → 38.8% (flat) | 37.2% | 0.197 |

ViT-B's flat validation accuracy across both epochs, combined with a
real explainability-sample check (`scripts/generate_explainability_samples.py`)
showing all 3 sampled predictions landed on `eucrite_like` at nearly
identical confidence (~0.57), is consistent with mode collapse — reported
here rather than smoothed over.

**Explainability**: Grad-CAM (`ml/explainability/gradcam.py`) was already
real, working code; verified again against the trained checkpoint. The
real fix this branch made: `attention_viz.py`'s attention-rollout hook
wiring (previously a documented TODO) — timm's default `fused_attn` path
never exposes attention weights to a plain forward hook, so each
attention block's `forward` is temporarily monkey-patched (restored via
try/finally) with a faithful reimplementation of the manual computation
path that captures the real softmax weights. Verified: 12 real
`(1, 12, 197, 197)` attention tensors from one real ViT-B forward pass, a
real 14×14 rollout heatmap, output unaffected, forward cleanly restored.

**Backend/frontend**: `backend/main.py` was already a real, working
`/predict` endpoint before this branch (not the "501 stub" the
originating task brief assumed — a real premise mismatch, documented
rather than forced); extended to support both model types and route to
the matching real explainability method, with the fixed disclaimer field
now also stating the synthetic-label caveat directly in the API
response. `frontend/src/App.tsx` (the real predict UI — the brief named
a separate `UploadPredict.tsx` that does not exist, a second documented
premise mismatch) was verified end-to-end via a real headless-browser
(Playwright) run against the real running backend: a real test crop
uploaded, a real prediction/heatmap/disclaimer rendered in the DOM, zero
console errors.

**Docker**: `docker-compose.yml` and both Dockerfiles already existed
(a third documented premise mismatch — the originating brief called them
"currently missing"). Verifying them by actually running them (not just
reading them) surfaced three real bugs, all fixed and re-verified: (1)
the backend image pulled ~1GB+ of unused GPU CUDA/cuDNN dependencies for
a CPU-only inference container, fixed with a CPU-only torch wheel index;
(2) `docker-compose.yml`'s referenced `.env` was never actually copied
from the pre-existing `.env.example`, fixed by doing so; (3) the
production frontend build (`vite build` + `serve -s dist`) has no
reverse proxy, unlike the dev server — a relative `/predict` call
silently returned the frontend's own HTML shell instead of the backend's
JSON — fixed with a build-time `VITE_API_BASE_URL`, re-verified with a
real Playwright run against the actual rebuilt container.

## Global-mosaic experiment (`final/mosaic-dataset`, post-closeout)

A later, separate experiment, branched off this closeout
(`final/closeout` → `final/mosaic-dataset`) and documented in full in
`docs/mosaic_experiment_log.md`. It does not touch or revise anything
above — month1's real spectral-crop pipeline, its CONFIRMED NEGATIVE
verdict, or the Month 2 engineering system are all unchanged. It asks a
different, narrower question: can a deep image model, trained on FC
global-mosaic tiles, learn to predict coarse VIR Band I center bins
better than a trivial brightness/location baseline, under a
leakage-safe (region-block) split?

**What the labels measure, stated plainly, as in every other section of
this report: Band I (pyroxene absorption) center-wavelength TERTILE
bins of the real VIR global mosaic (`ml/data/mosaic_labels.py`) — not
a validated mineral-composition classification.** Reusing this
project's own existing literature pointwise thresholds
(diogenite/howardite/eucrite, 0.92/0.95 µm) on this global raster was
tried first and produces a degenerate 1.14% / 98.86% / 0.00% split;
tertiles of the mosaic's own real distribution were used instead, and
the resulting class names (`band1_low`/`band1_mid`/`band1_high`) were
deliberately kept neutral so they are never mistaken for the validated
pointwise scheme used elsewhere in this project.

**Pipeline, gated at every stage**: real FC HAMO (USGS, 74.18 px/deg)
and real VIR Band I/II derived mosaics (`sbnarchive.psi.edu`
`DAWN-A-VIR-5-DDR-MOSAIC-V1.0`) acquired with recorded sha256/size
(Gate A pass); the FC/VIR longitude sign relationship was resolved
empirically against Rheasilvia's literature-documented diogenite
signature (not assumed — an initial test that omitted the real
Claudia-frame offset got the sign wrong and was caught and corrected
before being relied on); labels fixed and committed before any model
code; a confound screen (Gate B) trained a trivial baseline (logistic
regression / random forest on per-pixel albedo + lat/lon, real
region-block split) *before* any deep model, finding it already beats
the real majority-class rate (44.43%) by **+11.37 points** (55.80%
random forest) — i.e., mean FC albedo and latitude alone carry real
signal about these VIR tertile bins, the exact confound this report's
month1 track also had to repeatedly rule out for a different question.
1,494 real 224×224 FC tiles were cut and region-block split (20°
blocks, one-tile buffer, 70/15/15) to prevent spatial leakage between
train/val/test.

**Stage 4 (val-only tuning)**: staged transfer learning (ResNet-50,
ViT-B, ImageNet-pretrained, frozen-then-unfrozen) with 2 targeted
ablations run to completion — class-weighted loss for ResNet-50 (real
win: val balanced accuracy +8.61 pts, macro-F1 +12.25 pts over baseline,
at a small real calibration cost) and layer-wise LR decay for ViT-B
(real, honest negative result: every metric slightly worse than
baseline, so the named fix for Month 2's documented ViT mode collapse
did not transfer to this dataset). Augmentation, LR
schedule/warmup, label smoothing, early stopping, and temperature
scaling were not run, stated plainly as a real compute/time constraint,
not a judgment.

**Stage 5 (real test set, touched exactly once)** — 222 real test
tiles (`band1_low`=96, `band1_mid`=27, `band1_high`=99; majority-class
rate 44.59%):

| model | n | accuracy | balanced accuracy | macro-F1 | ECE |
|---|---|---|---|---|---|
| Trivial baseline (RF: albedo + lat/lon, refit on tiles) | 222 | 0.7162 | **0.5530** | **0.5374** | 0.1190 |
| ResNet-50 (class-weighted) | 222 | 0.5180 | 0.5067 | 0.4744 | 0.0765 |
| ViT-B (baseline) | 222 | 0.6261 | 0.4831 | 0.4636 | 0.0791 |
| Ensemble (averaged softmax) | 222 | 0.6216 | 0.5056 | 0.5072 | 0.0700 |

Confusion matrices (rows=true, cols=predicted,
`[band1_low, band1_mid, band1_high]`): trivial baseline
`[[82,2,12],[1,1,25],[16,7,76]]`; ResNet-50 (class-weighted)
`[[26,11,59],[4,13,10],[13,10,76]]`; ViT-B (baseline)
`[[58,0,38],[17,1,9],[18,1,80]]`; ensemble
`[[48,2,46],[11,4,12],[13,0,86]]`.

**Real, honest finding, not worked around**: on the real held-out test
set, no deep model beats the real trivial baseline on balanced accuracy
or macro-F1 — the metrics this experiment deliberately reports
alongside raw accuracy for exactly this reason. ViT-B's raw accuracy
(0.6261) looks like the second-best number, but its balanced accuracy
(0.4831) is the *worst* of the four, because it predicts `band1_mid`
almost never (1 of 27 correct) — a majority-class-dominated failure
mode that raw accuracy alone would have hidden. Grad-CAM (ResNet-50)
and attention rollout (ViT-B), run on 6 real test tiles (all
`band1_low` by manifest order, a disclosed sampling limitation, not a
cherry-pick), show Grad-CAM's brightest region consistently sitting on
the same bright albedo/shading ridge that is the most visually
prominent brightness feature in each raw tile — consistent with the
model tracking brightness/shading rather than an independently
compositional signal. ViT-B's attention rollout is diffuse and
corner-biased, consistent with its underperformance and this project's
separately documented ViT attention concerns.

**Conclusion**: at this real training budget, on this real tiling and
labeling scheme, a deep image model does not demonstrably learn these
VIR Band I tertile classes any better than a simple brightness +
location statistic — and on the real test set, slightly worse on the
metrics that matter most given the class imbalance. This strengthens,
rather than contradicts, this report's central finding above: apparent
signal in Dawn-derived spectral/compositional groupings on Vesta needs
to survive a real confound screen before being called a model result,
and in both the month1 spectral-crop track and this later image-tiling
experiment, it did not. Full real numbers, logs, and the acquisition/
label/split/training provenance for every claim above are in
`docs/mosaic_experiment_log.md`.

## Mosaic v2: removing the brightness shortcut (`final/mosaic-v2`)

A direct follow-up to the global-mosaic experiment above, branched off
`final/mosaic-dataset`. It does not revise anything above; it instead
asks the question the original experiment's single fixed test set could
not cleanly answer: is there *any* real configuration — of label task,
confound-removal technique, or ablation — under which a deep model
beats a properly-measured trivial baseline on this data? Full real
numbers, per-fold tables, and the provenance for every claim below are
in `docs/mosaic_v2_log.md`.

**The central new finding**: re-measuring the trivial baseline under
real **5-fold region-block cross-validation** instead of one fixed
split gives **0.7783 ± 0.0659 balanced accuracy** — far higher than the
original experiment's single-split number (0.5530) and not a bug
(region-block overlap between every fold's train/val/test was checked
and is zero). Isolating why, on the identical CV folds: albedo alone
reaches only 0.3690 and latitude alone only 0.4868, but **latitude +
longitude together, with zero pixel data, already reach 0.7215**. At
this task's 20°-block grid size, a tile's (lat, lon) address is itself
close to knowing which real Vesta geologic terrane produced its label —
this raised the real bar for every comparison that followed.

**Gate C (real FC color-filter data)**: real cylindrical mosaics for
three Dawn FC2 filters (749/917/965 nm, `sbnarchive.psi.edu`,
empirically longitude-verified — a different sign convention than
VIR's, confirmed rather than assumed) were acquired and tested as
additional features. They did not beat albedo+lat/lon by more than 1
CV standard deviation (−0.0258 points, i.e. slightly worse) — no extra
signal found, as this gate's own rule requires when that happens.

**Stage 2 (removing the brightness shortcut)** — every variant tested
under the same 5-fold CV, head-only budget: plain ResNet-50 (0.4530),
plain ViT-B (0.4579), per-tile albedo-normalized ResNet-50 (0.4698) and
ViT-B (0.4500), frozen-ImageNet-embedding hybrid (0.5630), and a
residual model with real albedo/lat/lon concatenated directly into the
classifier (**0.4913**, the best image-using configuration). Every one
remained far below the 0.7783 trivial baseline. Removing brightness
specifically (the albedo-normalized variants) changed almost nothing —
real evidence that brightness was not the shortcut being exploited in
the first place; the real shortcut, per Stage 0's own finding, is
location, and only the residual model (given that information
directly) closed any of the gap.

**Stage 3 (ablations against the Stage 2 winner)**: class-weighted loss
was a real, clean win (**0.5637 ± 0.0403**, +0.0724 over the residual
baseline, replicating `final/mosaic-dataset`'s own class-weighting
finding under a completely different protocol); augmentation was a
real, clean loss (0.4785, worse than even the plain residual baseline).
**Final best real configuration for this branch: residual ResNet-50 +
class-weighted loss, 0.5637 ± 0.0403 balanced accuracy.**

**Stage 4 (2-class task, thresholds reused unchanged, reported
separately)**: the same winning configuration reaches a higher raw
number on the easier 2-class task (0.6059) but falls *further* behind
its own trivial baseline (0.9391, a −0.3332 point gap vs. the 3-class
task's −0.2146) — simplifying the task did not help the deep model
catch up.

**Stage 5 (explainability)**: real Grad-CAM on 12 real test tiles,
stratified 4 per true class, against the final winning checkpoint.
Honest finding: the heatmaps are coarse, structurally similar,
largely content-independent patterns across tiles with very different
real terrain — unlike the original experiment's Grad-CAM maps, which
consistently tracked a real, visible brightness ridge. This is
consistent with the residual model's real predictive power coming
overwhelmingly from its side-input branch, not from content-dependent
visual features.

**Verdict, stated in one sentence as this stage's own instruction
requires**: **no** — nothing tested in this branch beat the real CV
trivial baseline by more than its own standard deviation, on either the
3-class task (best real result 0.5637 ± 0.0403 vs. 0.7783 ± 0.0659) or
the 2-class task (0.6059 ± 0.1027 vs. 0.9391 ± 0.0349) — the honest
result is a second, independent, and more rigorously-measured
confirmation that this data's real signal, at the tile scale and
compute budget tested here, is overwhelmingly positional and not
something a deep vision model recovers from pixels beyond what a
simple location-aware baseline already captures.

## Limitations and honest scope statement

- **This is a negative result for the compositional-signal question as
  tested, not a disproof of HED compositional variation existing on
  Vesta's surface.** It means: within this project's real acquisition
  (HAMO + LAMO, 5 real cycles/windows, 2,649 crops, 312 spectra, 141
  paired observations), no test performed across six independent
  confound-checking passes ever produced evidence favoring genuine
  composition over session timing or fit confidence as the driver of the
  observed Band II clustering.
- **The band-center fitting method, even after the v2 fix, flags every
  single real observation checked (23/23 in Slice 13, and implicitly all
  141 in Slice 16's larger sample) as carrying genuine fit ambiguity** —
  this project's spectral feature extraction may not be precise enough
  for this signal at this instrument's real noise floor, independent of
  acquisition design.
- **Geometry approximations carried through every slice, never
  re-examined**: equirectangular-box IoU for footprint overlap, a
  linear-footprint pixel mapping for crops, a specificity penalty
  calibrated against only the original `hamo_cycle1` sample's real
  size-ratio distribution (1.88x-4.04x) — not re-validated against
  Slice 16's larger, more diverse sample.
- **The engineering pipeline (Month 2) is mechanically validated, not
  scientifically validated** — every accuracy/confidence number there
  comes from synthetic labels and must never be read as a Vesta result.
- **No model was ever trained on real compositional labels** — Month 2
  and Month 3's original scope (`docs/month2_log.md`,
  `docs/month3_log.md`) was never reached on real data, because its
  prerequisite (an adequately diverse, confound-free real labeled
  sample) was never met.

## Future work

Named explicitly at the end of Slice 16, the two live routes if
compositional labeling is ever pursued on this data:

1. **A fundamentally different band-center-fitting method, proven robust
   to the confidence confound demonstrated here** (Slices 13 and 16 both
   show `compute_band_center_v2()`'s own per-sample confidence still
   correlates with cluster assignment at high significance) — e.g. a full
   Modified Gaussian Model fit (considered, not implemented, in Slice 13),
   or an independent noise-floor characterization against VIR's actual
   documented instrument specs rather than this project's illustrative
   perturbation models.
2. **An acquisition design that structurally decorrelates session timing
   from any candidate compositional signal** — e.g. repeated observations
   of the *same* ground track at deliberately different times of day —
   since every acquisition window tried in this project (5 real
   cycles/windows across two mission phases) showed the same ~85-92%
   session-cluster correlation.

Additional deferred items, traceable to this repo's own documented TODOs
(no external "proposal Section 4" document was found committed anywhere
in this repository to cite directly — this list is built from what is
actually committed):

- `ml/utils/splits.py`'s `assign_region_based_splits()` groups by spatial
  region only, not by spectrum product ID (Slice 10, Addendum 3) — a
  real split-leakage risk for any future real-label training, since 743+
  crops derive from a much smaller number of unique spectra.
- `ml/data/pds_acquisition.py`'s `_write_manifest()` append-without-dedup
  behavior (found and worked around in Slices 9, 11, and 16) — a proper
  code fix (dedup-on-write, or rebuild-from-scratch per run) was never
  implemented, by design, to keep that file's scope narrow across every
  slice that touched acquisition.
- `spatial_alignment.py`'s alignment-summary log-line format-string bug
  (noted, not fixed, in Slice 16) — see this branch's optional fix,
  documented in `docs/handoff/STATUS.md`'s final session entry.
- Per the engineering pipeline's own status doc: re-running v2 silhouette
  separately within HAMO and within LAMO (done, in Slice 16, specifically
  as the resolution to this item) and re-checking whether `confidence`
  should be propagated as a per-sample training weight rather than
  averaged away, if real labels are ever produced.
