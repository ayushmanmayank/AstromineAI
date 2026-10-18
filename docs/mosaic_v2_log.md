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

## Stage 1: Gate C — is there extra signal in real FC color-filter data?

### Real source

Checked directly against the real archive (`sbnarchive.psi.edu/pds3/dawn/fc/`):
the raw per-frame FC2 calibrated-image archives (`DWNxFC2_1A/1B.tgz`,
9–98 GB each) are far too large and are not mosaics; the real, usable
product is volume **`DWNVFC2_2`** (`DAWN-A-FC2-5-MOSAIC-V1.0`, "Dawn
FC2 High Level (2/3) Vesta Encounter Mosaics") — confirmed via its own
`AAREADME.TXT` (not a stub), `DATA/HAMO_COLOR/` holds real global
cylindrical mosaics (`VE_HAMO_00N_330E_CYL_FILTx.IMG`) for filters 2–8,
plus a ready-made Clementine-ratio composite (not used here; raw
filters give the task's own named ratio recipe directly). Recorded with
sha256/size in `datasets/mosaic/manifests/color_acquisition_manifest.json`:

| file | size (bytes) | sha256 | real center wavelength |
|---|---|---|---|
| `VE_HAMO_00N_330E_CYL_FILT3.IMG` | 1,426,367,448 | `8bf5b0cd...a3e55c4` | 749 nm |
| `VE_HAMO_00N_330E_CYL_FILT4.IMG` | 1,426,367,448 | `5dcc7588...09df974a` | 917 nm |
| `VE_HAMO_00N_330E_CYL_FILT5.IMG` | 1,426,367,448 | `58e2cfa0...47cd7d92b` | 965 nm |

**Real, caught-before-relying-on-it mistake**: an initial assumption,
based on a remembered generic Dawn FC filter table (F5≈758nm,
F7≈917nm, F8≈965nm), was used to start downloading F5/F7/F8 — a quick
byte-range probe of every real file's own label (cheap, no full
download needed) before relying on this gave the TRUE, label-confirmed
table instead: **F2=555nm, F3=749nm, F4=917nm, F5=965nm, F6=829nm,
F7=653nm, F8=438nm** — wavelength does not increase monotonically with
filter number in this instrument's real numbering. This task's own
"750/920 nm, 965/750 nm" ratio recipe therefore needs **F3, F4, F5**,
not F5/F7/F8. The wrong F7/F8 download was caught and stopped (after F5
had already finished, which turned out to still be needed) before
wasting further bandwidth; F3 and F4 were then downloaded instead.

### Reader + empirical format checks (`ml/data/mosaic_color_reader.py`, new file)

Same real PDS3 self-labeled-mosaic schema as VIR's (`LINES`,
`LINE_SAMPLES`, `SAMPLE_BITS=32`, `SAMPLE_TYPE=IEEE_REAL`,
`MISSING_CONSTANT=-1.0E+32`, `MAP_RESOLUTION`, `SIMPLE_CYLINDRICAL`,
same 255 km sphere), reused via import from
`ml/data/mosaic_reader.py` (that file itself left untouched). The one
real difference: this file's attached label (`RECORD_BYTES=106812`,
`LABEL_RECORDS=2` → 213,624 bytes) is larger than VIR's fixed
64,096-byte header, so a new reader discovers the real header size
from a small probe read rather than assuming a fixed size.

**Endianness re-confirmed empirically, not assumed to carry over from
VIR** (DLR vs. a different VIR-processing institution): big-endian
gives a clean, physically sane result (an 11.5%, clearly real nodata
population matching `MISSING_CONSTANT`, and the remaining pixels'
"sane-range" (|v|<100) values span 0.0–55.8 with mean 0.139 — a
realistic photometric reflectance distribution for Vesta); little-endian
gives nonsense (values near float32's ±3.4e38 range, NaN means from
overflow). Big-endian confirmed correct.

**Real, additional, undeclared-artifact finding**: beyond the labeled
`MISSING_CONSTANT`, ~55,221 of 356,511,753 pixels (0.0155%) in the real
F5 raster carry non-physical values (~1e29 scale) that are neither
close to the declared sentinel nor caught by a generic `>1e30` cutoff —
no other PDS3 null/saturation keyword (`CORE_NULL`,
`CORE_*_SATURATION`, etc.) is declared in the label either, so these are
real, undocumented artifacts, not a parsing bug. Handled with an
explicit, documented plausible-reflectance clip (`[0.0, 5.0]`) in
`scripts/mosaic_color_check.py`, kept separate from the generic reader
(which stays faithful only to the label's own declared sentinel).

### Real longitude-convention check (printed, same discipline as the original Rheasilvia check)

Since this is a broadband albedo image rather than a derived spectral
quantity, the check used here is structural cross-correlation against
the already-trusted FC clear-filter mosaic (not VIR's spectral-depth
argument) at 3 real, named features (Rheasilvia, Divalia Fossae,
Marcia), searching ±25 px locally for the best alignment (correcting
for the small 74.1765 vs. 74.1778 px/deg resolution mismatch between
this color volume and the primary 74ppd FC GeoTIFF):

| point | sign=+1 | sign=−1 |
|---|---|---|
| Rheasilvia | **+0.4031** | +0.2281 |
| Divalia Fossae | **+0.6226** | +0.1380 |
| Marcia | **+0.2419** | +0.2336 |

`lon_sign=+1` wins clearly at 2 of 3 points and ties at the third —
**the opposite sign from VIR's `-1`**, confirmed rather than assumed to
carry over (the PDS3 SIS leaves this implementation-defined per-dataset,
already documented in `ml/data/mosaic_reader.py`, and FC2's color
mosaics are a different processing pipeline than VIR's). The real
`-150°` Claudia-frame longitude offset DID carry over unchanged (beats
offset=0 at all 3 points: Rheasilvia +0.4031 vs. +0.0466; Divalia Fossae
+0.6226 vs. +0.3176; Marcia +0.2419 vs. +0.2194). Side-by-side check
images saved (not committed, gitignored like the original crater
checks): `datasets/mosaic/checks/{Rheasilvia,Divalia_Fossae}_fc_vs_fc2color_confirmed.png`.

### Real coverage + Gate C result (`scripts/mosaic_color_check.py`)

Real per-band valid-pixel coverage (full mosaic): F3 88.48%, F4 88.39%,
F5 88.45% — real and incomplete, as `AAREADME.TXT` documents (HAMO-1
cycle 1/6 full color for the south, HAMO-2 cycle 6 only for the north,
poor illumination at high latitudes; LAMO color excluded entirely from
this volume for coverage reasons). Of the real 1,494 Stage-3 tiles,
**1,393 have full F3+F4+F5 coverage** (101 missing at least one band).

Real per-tile color-ratio features: `ratio1 = F3/F4` (~750/920 nm),
`ratio2 = F5/F3` (~965/750 nm), each a real 11×11-pixel local-window
mean (not a single pixel) around the tile's center, looked up via the
confirmed `lon_sign=+1, lon_offset=-150°` conversion. Random forest,
same 5-fold region-block CV (recomputed over the 1,393-tile coverage
subset, so the comparison is apples-to-apples — the trivial baseline's
CV number is slightly different here than Stage 0's full-1,494-tile
number, both reported honestly):

| features (1,393-tile coverage subset) | balanced accuracy (mean ± std) | macro-F1 (mean ± std) |
|---|---|---|
| albedo + lat/lon only | 0.7486 ± 0.0682 | 0.7461 ± 0.0688 |
| albedo + lat/lon + color-ratios | 0.7228 ± 0.0715 | 0.7244 ± 0.0710 |

Gain from adding color-ratio features: **−0.0258** balanced-accuracy
points (color-ratios made it slightly *worse*), against 1 std of the
albedo+lat/lon CV spread = 0.0682.

**GATE C verdict: color-ratio features do NOT beat the albedo+lat/lon
baseline by more than 1 std of the CV spread — no extra signal in
available FC color data.** Stated plainly, not reasoned around:
whatever real information F3/F4/F5 broadband reflectance ratios carry
about these VIR Band I tertile labels is already redundant with (or
weaker than) what clear-filter albedo + location already capture, at
least for the real ~88%-coverage subset tested, under the real
compute/data limits of this check. Stage 2 and 3 proceed on the
existing single-band (clear-filter) FC tiles only, per this gate's
instruction.

## Stage 2: removing the brightness shortcut

Real, stated compute-budget decision for all of Stage 2 and 3: 5-fold
CV multiplies training cost 5x over `final/mosaic-dataset`'s
single-split runs, so every CNN/ViT run in this stage is a **head-only
probe** (frozen ImageNet-pretrained backbone, 2 epochs, no unfreeze
stage) — a disclosed trade-off, not a silent shortcut. This still
answers the real question ("does the model see anything in the pixels
beyond albedo+lat/lon") since a frozen-backbone head on real ImageNet
features is a meaningful probe of what visual information is already
present, and it is directly comparable across every variant/ablation
reported here (same budget throughout). `final/mosaic-dataset`'s Stage
4 full staged fine-tune (`resnet50_classweighted.pt`, 2+2 epochs,
single split) remains the separate reference for what full fine-tuning
can do on that fixed test set.

### Stage 2(c): hybrid — frozen ImageNet ResNet-50 embeddings + albedo + lat/lon (random forest)

Deliberately uses an off-the-shelf, never-Vesta-fine-tuned ResNet-50
backbone (not `final/mosaic-dataset`'s `resnet50_classweighted.pt`
checkpoint, which was fit on a *different* train/val/test split that
overlaps with this task's new CV test folds — reusing it here would
leak real label information into a supposedly "frozen" extractor). A
real, stated trade-off: zero leakage risk, but no Vesta-adapted feature
space either.

| fold | n_test | accuracy | balanced accuracy | macro-F1 |
|---|---|---|---|---|
| 0 | 292 | 0.5925 | 0.5028 | 0.4523 |
| 1 | 307 | 0.8502 | 0.6055 | 0.6077 |
| 2 | 304 | 0.7500 | 0.5613 | 0.5499 |
| 3 | 295 | 0.7864 | 0.6267 | 0.5851 |
| 4 | 296 | 0.6182 | 0.5187 | 0.4720 |
| **mean ± std** | | 0.7195 ± 0.0989 | **0.5630 ± 0.0479** | 0.5334 ± 0.0613 |

**Real, honest negative result**: raw, off-the-shelf ImageNet visual
features *combined with* albedo+lat/lon score **worse** than
albedo+lat/lon alone (0.5630 vs. 0.7783 trivial baseline, a −0.2153
point difference — not a rounding-level gap). Plausible real cause,
stated as a hypothesis, not proven here: 2048-dimensional raw ImageNet
features, added on top of the 4 side features, give the random forest
far more irrelevant dimensions to fit with only ~900-1000 real training
tiles per fold, diluting rather than adding to the strong, low-
dimensional location/albedo signal already identified in Stage 0 — i.e.
unprocessed generic visual features are not a shortcut to a better
model here, at least not through a plain random forest on top of them.

### Stage 2 baseline (head-only CV reference, plain tiles) — ResNet-50

The reference point every Stage 2(a) albedo-normalization comparison
is measured against: same head-only, 2-epoch, 5-fold-CV budget, plain
(non-normalized) tiles.

| fold | n_test | majority rate | accuracy | balanced accuracy | macro-F1 | ECE |
|---|---|---|---|---|---|---|
| 0 | 292 | 0.4863 | 0.3973 | 0.3478 | 0.2760 | 0.2104 |
| 1 | 307 | 0.6124 | 0.7068 | 0.4629 | 0.4528 | 0.1428 |
| 2 | 304 | 0.4605 | 0.6316 | 0.4676 | 0.4376 | 0.0440 |
| 3 | 295 | 0.5356 | 0.6000 | 0.5038 | 0.4943 | 0.0353 |
| 4 | 296 | 0.4797 | 0.5878 | 0.4829 | 0.4272 | 0.0840 |
| **mean ± std** | | | 0.5847 ± 0.1025 | **0.4530 ± 0.0545** | 0.4176 ± 0.0744 | 0.1033 ± 0.0656 |

Real result, consistent with `final/mosaic-dataset`'s own Stage 4/5
findings: a head-only ResNet-50 is **well below** the CV trivial
baseline (0.4530 vs. 0.7783, a −0.3253 point gap) — a plain CNN probe,
even under this task's harder real CV bar, does not come close to what
albedo+lat/lon alone already captures.

### Stage 2 baseline (head-only CV reference, plain tiles) — ViT-B

| fold | n_test | majority rate | accuracy | balanced accuracy | macro-F1 | ECE |
|---|---|---|---|---|---|---|
| 0 | 292 | 0.4863 | 0.3630 | 0.3656 | 0.3504 | 0.1698 |
| 1 | 307 | 0.6124 | 0.6971 | 0.5194 | 0.5204 | 0.0244 |
| 2 | 304 | 0.4605 | 0.6053 | 0.4478 | 0.4306 | 0.0516 |
| 3 | 295 | 0.5356 | 0.5763 | 0.4810 | 0.4629 | 0.0487 |
| 4 | 296 | 0.4797 | 0.5507 | 0.4757 | 0.4414 | 0.1611 |
| **mean ± std** | | | 0.5585 ± 0.1095 | **0.4579 ± 0.0515** | 0.4411 ± 0.0550 | 0.0911 ± 0.0615 |

Real result: essentially the same story as ResNet-50's baseline
(0.4579 vs. 0.7783 trivial baseline, −0.3204 points) — slightly less
bad than ResNet-50's head-only probe (−0.3253), but both arms are
roughly 30 points below the real CV trivial baseline, and neither
shows the severe `band1_mid`-ignoring mode-collapse `final/mosaic-dataset`'s
ViT-B arm showed under its own, different (single-split) protocol —
both confusion matrices here do populate the middle class to some real
degree in most folds.

### Stage 2(a): per-tile albedo normalization — ResNet-50

Real per-tile histogram equalization (removes each tile's own overall
brightness level/contrast before the model ever sees it), same
head-only, 2-epoch, 5-fold-CV budget as the baseline above, compared
directly against it (same architecture, same real tiles, only the
pixel preprocessing differs):

| fold | n_test | accuracy | balanced accuracy | macro-F1 | ECE |
|---|---|---|---|---|---|
| 0 | 292 | 0.4247 | 0.3739 | 0.2928 | 0.1499 |
| 1 | 307 | 0.7231 | 0.5092 | 0.5262 | 0.1558 |
| 2 | 304 | 0.6513 | 0.4812 | 0.4545 | 0.0770 |
| 3 | 295 | 0.6407 | 0.5115 | 0.4689 | 0.0902 |
| 4 | 296 | 0.5676 | 0.4729 | 0.4112 | 0.1064 |
| **mean ± std** | | 0.6015 ± 0.1012 | **0.4698 ± 0.0502** | 0.4307 ± 0.0782 | 0.1159 ± 0.0317 |

**Real result: a marginal, noise-level change** — 0.4698 vs. the plain
baseline's 0.4530 (+0.0168 points, well under either arm's own ~0.05
std) — still ≈0.31 points below the CV trivial baseline (−0.3085 vs.
baseline's −0.3253). Removing raw brightness from the tiles neither
helps nor meaningfully hurts a head-only ResNet-50 here, consistent
with Stage 0's finding that the real signal this task's labels carry is
overwhelmingly positional, not a brightness cue the model could have
been leaning on in the first place — there is little brightness-driven
performance left to remove.

### Stage 2(a): per-tile albedo normalization — ViT-B

| fold | n_test | accuracy | balanced accuracy | macro-F1 | ECE |
|---|---|---|---|---|---|
| 0 | 292 | 0.4349 | 0.3938 | 0.3938 | 0.1265 |
| 1 | 307 | 0.6580 | 0.4677 | 0.4602 | 0.0493 |
| 2 | 304 | 0.5987 | 0.4609 | 0.4530 | 0.0689 |
| 3 | 295 | 0.5831 | 0.4769 | 0.4703 | 0.0780 |
| 4 | 296 | 0.5439 | 0.4507 | 0.3978 | 0.1663 |
| **mean ± std** | | 0.5637 ± 0.0741 | **0.4500 ± 0.0294** | 0.4350 ± 0.0325 | 0.0978 ± 0.0427 |

**Real result: again essentially flat** vs. ViT-B's plain baseline
(0.4500 vs. 0.4579, a −0.0079 point difference, noise-level) — −0.3283
vs. the CV trivial baseline. Same conclusion as the ResNet-50 arm:
albedo normalization does not meaningfully change what either
architecture learns here, consistent with the real signal being
positional rather than brightness-driven in the first place.

**Stage 2(a) summary verdict**: per-tile albedo normalization does
**not** beat the plain-tile baseline for either architecture — both
differences are within a single fold's own standard deviation, i.e.
indistinguishable from noise at this CV budget. Brightness was not a
shortcut either architecture was meaningfully exploiting to begin with
(Stage 0's own evidence: albedo alone only reaches 0.3690 balanced
accuracy, far below location's 0.7215), so removing it changes little.

### Stage 2(b): residual model — ResNet-50 + real side inputs (albedo, lat, sin/cos lon) concatenated before the classifier

| fold | n_test | accuracy | balanced accuracy | macro-F1 | ECE |
|---|---|---|---|---|---|
| 0 | 292 | 0.4452 | 0.4294 | 0.4191 | 0.1230 |
| 1 | 307 | 0.7068 | 0.4797 | 0.4865 | 0.1276 |
| 2 | 304 | 0.6908 | 0.5260 | 0.5234 | 0.1169 |
| 3 | 295 | 0.6576 | 0.5238 | 0.4688 | 0.0374 |
| 4 | 296 | 0.5811 | 0.4979 | 0.4416 | 0.1452 |
| **mean ± std** | | 0.6163 ± 0.0959 | **0.4913 ± 0.0354** | 0.4679 ± 0.0361 | 0.1100 ± 0.0375 |

**Real result: the best of every Stage 2 variant tested** (0.4913 vs.
plain ResNet-50's 0.4530, albedo-norm ResNet-50's 0.4698, plain ViT-B's
0.4579, albedo-norm ViT-B's 0.4500) — a genuine, non-noise-level
improvement (+0.0383 over plain ResNet-50, more than half a fold's own
std). Giving the model direct access to the same real positional
features the trivial baseline itself uses clearly helps, which makes
sense: a CNN cannot recover absolute (lat, lon) from image content
alone (crater shapes do not uniquely encode global position without
recognizing specific, individually-identified landmarks), so handing
it that information explicitly closes part of the gap.

**But it still falls well short of the pure trivial baseline**
(0.4913 vs. 0.7783, a −0.2870 point gap — smaller than every other
variant's gap, but still large). A real, honest, plausible explanation,
stated as a hypothesis rather than proven here: a frozen-backbone
linear head learning a joint decision boundary over 2048 largely-
irrelevant CNN dimensions plus 4 real, highly-informative side-input
dimensions, under only 2 head-only epochs, does not weight those 4
dimensions as effectively as a random forest given only those same 4
dimensions and no distracting high-dimensional noise. This is not
evidence that the CNN's own visual features are adding anything real —
if they were, the residual model should have come *closer to or beaten*
the trivial baseline, not merely improved on the CNN-alone arms while
remaining far below it.

### Stage 2 summary + winner for Stage 3

| variant | balanced accuracy (mean ± std) | vs. CV trivial baseline (0.7783 ± 0.0659) |
|---|---|---|
| Baseline ResNet-50 | 0.4530 ± 0.0545 | −0.3253 |
| Baseline ViT-B | 0.4579 ± 0.0515 | −0.3204 |
| Albedo-normalized ResNet-50 | 0.4698 ± 0.0502 | −0.3085 |
| Albedo-normalized ViT-B | 0.4500 ± 0.0294 | −0.3283 |
| Hybrid (frozen ImageNet embeddings + RF) | 0.5630 ± 0.0479 | −0.2153 |
| **Residual (ResNet-50 + side inputs)** | **0.4913 ± 0.0354** | **−0.2870** |

Real, honest Stage 2 verdict: **every single variant remains well
below the CV trivial baseline.** None of this stage's confound-removal
attempts turned up a configuration where the deep model sees something
in the pixels beyond what albedo+lat/lon already capture — if anything,
the clearest lesson is that handing the model the trivial features
directly (Stage 2(b)) helps more than anything the CNN extracts from
pixels on its own. The **hybrid variant (0.5630)** is nominally the
least-bad CNN-involving result in raw number, but it uses no Vesta
training at all (an off-the-shelf frozen embedding) and was already
reported in Stage 2(c) as a real negative relative to the trivial
baseline alone. Per this task's instruction to carry forward "the best
Stage 2 variant" for Stage 3's ablations, **residual ResNet-50
(0.4913 ± 0.0354)** is used — it is the best real, Vesta-trained,
image-using configuration, even though the margin over the other
image-using arms is real but modest, and none of them is close to
competitive with the trivial baseline.

## Stage 3: targeted ablations against the Stage 2 winner (residual ResNet-50)

Two ablations chosen (not the full menu of seven, per this project's
established "two targeted ablations, not exhaustive, given real
compute constraints" precedent from `final/mosaic-dataset`'s own Stage
4): **class-weighted loss** (a real, clean win there: +8.61 pts
balanced accuracy for plain ResNet-50) and **augmentation** (not yet
tested anywhere in this branch). Not run, stated plainly, for the same
real compute/time reason: LR schedule+warmup, label smoothing, early
stopping, balanced sampling/focal loss, ViT-B fix attempts, temperature
scaling — all implemented and available via `scripts/mosaic_train_cv.py`'s
flags for a future run, just not exercised here.

### Ablation 1 — class-weighted loss

| fold | n_test | accuracy | balanced accuracy | macro-F1 | ECE |
|---|---|---|---|---|---|
| 0 | 292 | 0.3938 | 0.4888 | 0.3987 | 0.1415 |
| 1 | 307 | 0.6710 | 0.5784 | 0.5160 | 0.0947 |
| 2 | 304 | 0.6743 | 0.5865 | 0.5733 | 0.1243 |
| 3 | 295 | 0.6034 | 0.5588 | 0.5464 | 0.0584 |
| 4 | 296 | 0.6216 | 0.6057 | 0.5846 | 0.0683 |
| **mean ± std** | | 0.5928 ± 0.1032 | **0.5637 ± 0.0403** | 0.5238 ± 0.0669 | 0.0974 ± 0.0318 |

**Real, clean ablation win** — the best result of this entire branch so
far: 0.5637 vs. the residual baseline's 0.4913 (+0.0724 points, well
beyond either arm's own std), closing the gap to the CV trivial
baseline to −0.2146 (from −0.2870). Consistent with
`final/mosaic-dataset`'s own finding that class-weighting helps this
dataset's real class imbalance (`band1_mid` underrepresented by the
tiling's majority-vote labeling), replicated here under a completely
different (CV, not single-split) protocol and a different base
architecture (residual, not plain ResNet-50) — a real, robust finding,
not a one-off.

### Ablation 2 — augmentation (flip/rotate/brightness jitter)

| fold | n_test | accuracy | balanced accuracy | macro-F1 | ECE |
|---|---|---|---|---|---|
| 0 | 292 | 0.4281 | 0.4452 | 0.4206 | 0.1351 |
| 1 | 307 | 0.6384 | 0.3958 | 0.3876 | 0.1215 |
| 2 | 304 | 0.6875 | 0.5323 | 0.5298 | 0.1093 |
| 3 | 295 | 0.6678 | 0.5350 | 0.4766 | 0.0799 |
| 4 | 296 | 0.5676 | 0.4840 | 0.4194 | 0.1295 |
| **mean ± std** | | 0.5979 ± 0.0941 | **0.4785 ± 0.0530** | 0.4468 ± 0.0504 | 0.1151 ± 0.0196 |

**Real, honest negative result**: augmentation makes things *worse*
than the plain residual baseline (0.4785 vs. 0.4913, a −0.0128 point
drop) and far worse than class-weighting (0.5637) — −0.2998 vs. the CV
trivial baseline, the largest gap of any Stage 3 result. A plausible
real explanation, not proven here: with only 2 head-only epochs, the
extra variance augmentation introduces (random flip/rotation/brightness
jitter) leaves too little real training signal for the model to
converge on, and this dataset's real signal is overwhelmingly
positional (Stage 0), not a visual pattern augmentation could help
generalize.

### Stage 3 verdict

**Class-weighted loss is a real, clean win; augmentation is a real,
clean loss.** Per this task's rule ("do not stack more than what wins
individually"), only class-weighting carries forward:

| config | balanced accuracy (mean ± std) | vs. CV trivial baseline |
|---|---|---|
| Residual ResNet-50 (Stage 2 winner) | 0.4913 ± 0.0354 | −0.2870 |
| + class-weighted loss | **0.5637 ± 0.0403** | **−0.2146** |
| + augmentation (instead) | 0.4785 ± 0.0530 | −0.2998 |

**Final best real configuration for this branch: residual ResNet-50 +
class-weighted loss, 0.5637 ± 0.0403 balanced accuracy** — still well
below the CV trivial baseline (0.7783 ± 0.0659), but the best any
image-using model achieved under this task's real compute budget.

## Stage 4 (optional task variant, run early for convenience): 2-class trivial baseline

Reported separately from every 3-class number in this log, per this
stage's own rule. Reuses `final/mosaic-dataset`'s already-fixed,
already-committed Band I center tertile thresholds unchanged (no new
threshold computed) — `ml/data/mosaic_labels_v2.py` simply drops the
middle tertile (`band1_mid`) and keeps the two extremes
(`band1_low`/`band1_high`), committed before any training on it, per
this task's rule. 1,299 of 1,494 real tiles remain (195 `band1_mid`
tiles dropped).

| fold | n_test | majority rate | balanced accuracy | macro-F1 |
|---|---|---|---|---|
| 0 | 263 | 0.5513 | 0.8807 | 0.8744 |
| 1 | 256 | 0.5039 | 0.9179 | 0.9179 |
| 2 | 262 | 0.5076 | 0.9730 | 0.9733 |
| 3 | 258 | 0.5155 | 0.9570 | 0.9573 |
| 4 | 260 | 0.7231 | 0.9669 | 0.9709 |
| **mean ± std** | | | **0.9391 ± 0.0349** | 0.9388 ± 0.0378 |

Real, expected finding: the 2-class task (the two most extreme tertile
bins only) is dramatically easier than the 3-class task even for the
trivial baseline (0.9391 vs. the 3-class trivial baseline's 0.7783) —
unsurprising, since dropping the ambiguous middle bin removes most of
the real classes' overlap in albedo/location space. This raises the
bar for any 2-class deep-model comparison correspondingly higher; see
the Stage 4 section below for the deep-model result against this real
number.

### Stage 4: 2-class deep model (winning config — residual ResNet-50 + class-weighted loss)

| fold | n_test | majority rate | accuracy | balanced accuracy | macro-F1 | ECE |
|---|---|---|---|---|---|---|
| 0 | 263 | 0.5513 | 0.4335 | 0.4326 | 0.4319 | 0.2631 |
| 1 | 256 | 0.5039 | 0.5508 | 0.5539 | 0.4680 | 0.1364 |
| 2 | 262 | 0.5076 | 0.7290 | 0.7255 | 0.7124 | 0.0951 |
| 3 | 258 | 0.5155 | 0.6589 | 0.6665 | 0.6408 | 0.0864 |
| 4 | 260 | 0.7231 | 0.7000 | 0.6512 | 0.6429 | 0.0545 |
| **mean ± std** | | | 0.6144 ± 0.1088 | **0.6059 ± 0.1027** | 0.5792 ± 0.1092 | 0.1271 ± 0.0728 |

**Real, honest finding**: the deep model's raw balanced accuracy is
higher here (0.6059) than on the 3-class task (0.5637) — the 2-class
task is simply easier — but the **gap to the trivial baseline is
larger, not smaller** (−0.3332 vs. the 3-class task's −0.2146), because
the trivial baseline improves even more on the easier task (0.7783 →
0.9391, +0.1608) than the deep model does (0.5637 → 0.6059, +0.0422).
Simplifying the task does not help the deep model catch up — if
anything it falls further behind in relative terms. This is reported
as a separate task's result, per this stage's own rule, and is not
mixed with the 3-class numbers anywhere in this log or the final
report.

## Stage 5: explainability + final report

### Checkpoint

One real checkpoint trained for explainability, since 5-fold CV trains
a fresh model per fold by design (no single "the" model otherwise):
this branch's winning real 3-class configuration (residual ResNet-50 +
class-weighted loss), trained on fold 0's real train+val tiles only
(`scripts/mosaic_train_cv.py --single-fold 0 --checkpoint-out
trained_models/mosaic_v2/residual_resnet50_classweighted_fold0.pt`).
That fold's own real test-fold metrics (not the CV mean — a single
fold's number, reported for transparency, not as this branch's headline
result): accuracy=0.3938, balanced_accuracy=0.4888, macro_f1=0.3987,
confusion matrix `[[41,27,74],[6,41,1],[12,57,33]]`.

### Grad-CAM on 12 real test tiles, stratified by true class (4 per class)

Reused `ml/explainability/gradcam.py`'s `generate_gradcam()`
unmodified (same as `final/mosaic-dataset`'s own Stage 5). Only
Grad-CAM, not attention rollout: this branch's winning configuration is
ResNet-50-based (the residual variant), not ViT-B, so attention
rollout does not apply to the real model being explained here — stated
plainly rather than run on an architecture that was not this branch's
real winner. 12 real tiles drawn from fold 0's real, held-out test set
(never used in that checkpoint's training), 4 per true class:
`band1_low` (tiles 00053, 00097, 00098, 00099), `band1_mid` (00102,
00786, 00991, 00992), `band1_high` (00046, 00047, 00054, 00081).
Images: `docs/handoff/artifacts/mosaic_v2_explainability/`. Real
predictions on these 12 (4/12 = 33.3% correct on this small stratified
sample): `band1_low` 2/4 correct (00098, 00099; 00053 and 00097
predicted `band1_high`), `band1_mid` 1/4 correct (00786; the other 3
predicted `band1_low`), `band1_high` 1/4 correct (00046; the other 3
predicted `band1_low`) — roughly consistent with this fold's own real
test-set accuracy (0.3938), allowing for the small, non-representative
12-tile sample.

**Honest visual assessment**: across all 12 tiles, the Grad-CAM heatmaps
are coarse, low-resolution, blocky patterns (ResNet-50's `layer4`
feature map is only 7×7 for a 224×224 input, upsampled by nearly 32×
to produce the final heatmap) that look **structurally similar across
tiles with very different real content** — a recurring vertical
bright band flanked by darker corners, present whether the tile shows a
sharp crater rim, smooth undifferentiated terrain, or mottled
small-scale texture, and regardless of the tile's true class or whether
the prediction was correct. This is a real, honest, negative finding
for interpretability: the highlighted regions do not look like they
track specific, content-dependent compositional or even albedo/shading
features the way `final/mosaic-dataset`'s own Stage 5 Grad-CAM maps did
(those consistently tracked a real, visible brightness ridge in each
tile). It is consistent with, and strengthens, Stage 2(b)'s own
hypothesis: this residual model's real predictive power comes
overwhelmingly from its side-input branch (the same real albedo+lat/lon
features the trivial baseline uses), with the CNN branch contributing a
comparatively weak, largely content-independent signal — exactly what
a near-identical heatmap across very different real tiles would look
like if the convolutional branch's gradient contribution to the final
decision were small relative to the side-input branch's.
