# Global-mosaic dataset v2: beating the trivial baseline honestly

Append-only working log for `final/mosaic-v2` (branched off
`final/mosaic-dataset`). Does not modify `docs/month1_log.md`,
`datasets/metadata/sample_metadata.csv`, `ml/data/spatial_alignment.py`,
`ml/utils/splits.py`, or any committed Stage 1-5 result/threshold from
`final/mosaic-dataset` — see that branch's own
`docs/mosaic_experiment_log.md` for the unchanged, prior results this
log builds on (fixed 222-tile test set: trivial baseline balanced
accuracy 0.5530 / macro-F1 0.5374, quoted here as this task's named bar
but **not** the CV reference number computed below).

## Stage 0: CV infrastructure

### Step 1 — `ml/utils/mosaic_cv.py`

New, separate module (built on `ml/utils/mosaic_splits.py`'s existing
`RegionBlock`/`region_block_for`/`is_buffered_out`, reused unmodified —
same 20° block grid, same one-tile buffer rule). `assign_fold_blocks()`
generalizes `mosaic_splits.py`'s greedy-deficit train/val/test assigner
to N folds. `make_cv_folds()` builds 5 outer folds; for outer fold *i*,
test = fold *i*'s tiles (touched once, as that fold's test set), val =
fold `(i+1) % 5` (rotating, inner-only — the only fold any tuning
decision may look at for that outer split), train = the other 3 folds.
9 new tests in `tests/test_mosaic_cv.py`, all passing: no train/val/test
overlap within a fold, no tile overlap across splits at the block level,
buffer respected (a known near-edge tile is never assigned to any fold
role), every tile used as the outer test fold exactly once across the 5
splits, deterministic given a seed.

Applied to the real, full pool of 1,494 non-buffered tiles from
`datasets/mosaic/manifests/tile_manifest.csv` (the original
train+val+test rows combined; CV re-splits them itself; `buffered_out`
rows excluded, same tiles the original pipeline already dropped for the
same reason), `block_size_deg=20.0`, `tile_size_deg=224/74.1778≈3.0213`,
`seed=42`: fold sizes (test) are 292/307/304/295/296 tiles, with
97/94/95/90/86 train blocks, 27/33/26/38/30 val blocks, 30/27/33/26/38
test blocks per fold respectively — **verified directly** (not just
asserted by the tests) that no region block ever appears in more than
one role within a fold (`train_blocks & val_blocks`,
`train_blocks & test_blocks`, `val_blocks & test_blocks` all empty, all
5 folds).

### Step 2 — trivial baseline recomputed under CV (`scripts/mosaic_cv_trivial_baseline.py`)

Real per-tile features (each tile's own mean FC pixel value as
"albedo", plus its real center lat/lon — same recipe as
`final/mosaic-dataset`'s Stage 5 test evaluation), fit on
train+val combined per outer fold (no real hyperparameters to tune for
a trivial model, so the inner val fold is folded into the fit rather
than held out uselessly), evaluated on that fold's outer test set
exactly once:

| model | balanced accuracy (mean ± std) | macro-F1 (mean ± std) |
|---|---|---|
| Logistic regression | 0.5800 ± 0.0397 | 0.5474 ± 0.0389 |
| Random forest | **0.7783 ± 0.0659** | **0.7815 ± 0.0678** |

Per-fold random forest balanced accuracy: `[0.8198, 0.7698, 0.6856,
0.8773, 0.7390]` (folds 0–4). Per-fold majority-class rate:
`[0.4863, 0.6124, 0.4605, 0.5356, 0.4797]`.

**This is dramatically higher than the fixed-split number (0.5530)
this task's own brief quotes as the bar — and that gap is itself the
most important finding of this stage, not a bug.** Verified directly,
not assumed: region-block-level overlap between every fold's
train/val/test sets is empty (checked above); the CV module's own 9
tests pass. The real cause, isolated directly by re-running the same
random forest on feature subsets under the identical CV folds:

| features | balanced accuracy (mean ± std) |
|---|---|
| latitude only | 0.4868 ± 0.0510 |
| albedo only | 0.3690 ± 0.0115 |
| latitude + sin/cos longitude (**no albedo, no pixels at all**) | **0.7215 ± 0.0961** |
| albedo + latitude + sin/cos longitude (full trivial baseline) | 0.7783 ± 0.0659 |

**Honest interpretation, stated plainly**: most of the trivial
baseline's real power comes from knowing *where on Vesta a tile is*
(latitude and longitude jointly), not from brightness. Latitude alone
is weak (0.49, barely above chance); albedo alone is weak (0.37); but
location alone — zero pixel data, zero albedo — already reaches 0.72.
This is a close-to-tautological consequence of how the labels
themselves were built: VIR Band I center is a real, spatially smooth,
large-scale geochemical map of Vesta (large real terranes — e.g. the
Rheasilvia basin's diogenite-rich material — occupy broad, contiguous
regions), and this task's own 20°-block grid is large enough that
knowing a tile's (lat, lon) address is itself close to knowing which
real geologic terrane produced its label, with no need to look at the
image at all. The one-tile buffer (≈3°) removes tiles immediately
adjacent to a block boundary, but a test block's *interior* can still
sit roughly 6° (two tile-widths) from a same-latitude-band training
block's interior in a different, non-adjacent longitude cell — close
enough, given the real spatial-correlation length scale of this
smoothed mosaic, for location alone to carry most of the real label
information.

**Consequence for the rest of this task, stated now rather than
discovered late**: "beating the trivial baseline" at the *tile* level
is a much higher bar than this task's brief's named number (0.5530)
suggests, and most of the real, true signal available to any model —
deep or trivial — at this block size is positional, not compositional
or visual. A vision model that merely learns to associate FC tile
appearance with its approximate location (plausible, since Vesta's
real surface albedo units are themselves geographically clustered) could
match this number without learning anything the trivial baseline
doesn't already capture more directly and more simply. Stage 2's
explainability-oriented variants (per-tile albedo normalization,
residual/side-input models, hybrid frozen-embedding models) are
designed with this specifically in mind — the real question is not just
"can a CNN beat 0.78 balanced accuracy" but "does a CNN see anything in
the pixels beyond what location already tells us," and Stage 2 reports
the side-inputs-only (location/albedo) model's own CV score next to
every image-based variant for exactly this reason.

**Reference numbers for the rest of this task**: random forest
(albedo + lat/lon) **0.7783 ± 0.0659 balanced accuracy, 0.7815 ± 0.0678
macro-F1** is the primary CV trivial-baseline bar quoted alongside
every later result (mirroring `final/mosaic-dataset`'s own convention
of quoting the random forest number as the primary trivial baseline).
Logistic regression (0.5800 ± 0.0397 / 0.5474 ± 0.0389) and the
location-only random forest (0.7215 ± 0.0961 / not separately computed
for macro-F1 here, see raw output) are reported alongside for context.
The majority-class rate (mean across folds, from the per-fold numbers
above) is reported next to every result too, per this task's rule.
