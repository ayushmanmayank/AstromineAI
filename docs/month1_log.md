# Month 1 Progress Log

## Slice 1: Verified data acquisition (Vesta, Dawn FC + Dawn VIR)

Scope: PDS data acquisition only. No spatial alignment, labeling, or
dataset splitting in this slice — that's next.

### Tasks

- [x] Locate the current live NASA PDS archive location(s) for Dawn
      mission Vesta-phase data.
- [x] Fetch and verify `AAREADME.TXT`, `INDEX/INDEX.TAB` +
      `INDEX/INDEX.LBL`, and `DOCUMENT/SIS/` for each volume used
      (`DWNVFC2_1B`, `DWNVVIR_V1A`, `DWNVVIR_I1A`) — all returned HTTP 200
      before any URL was written to config.
- [x] Implement `fetch_framing_camera_images()` in
      [`ml/data/pds_acquisition.py`](../ml/data/pds_acquisition.py).
- [x] Implement `fetch_vir_spectra()` in the same file.
- [x] Update `configs/config.yaml` `data.sources` with confirmed,
      working PDS URLs (no more TODO placeholders).
- [x] Run the acquisition script end-to-end with `--limit 10` to confirm
      it works before a full pull.
- [x] Update this log with confirmed URLs and download counts.

**2026-08-27 update:** re-verified against an explicit set of volume IDs
(`DWNVFC2_1B` for FC; `DWNVVIR_V1A` / `DWNVVIR_I1A` — raw/EDR — for VIR,
rather than the calibrated `*_1B` VIR volumes used in the first pass).
`fetch_vir_spectra()` and `configs/config.yaml` were restructured to
support both `raw` and `calibrated` levels per channel; `raw` is now the
configured default for VIR, matching these verified sources. FC is
unchanged (still defaults to calibrated `DWNVFC2_1B`).

Not started (intentionally, per scope): `spatial_alignment.py`,
`splits.py`, any labeling logic.

### PDS node investigation — confirmed 2026-08-26

Checked all three candidate nodes named in the task:

| Node | Result |
|---|---|
| `pds-geosciences.wustl.edu` | **Does not host Dawn FC/VIR.** `https://pds-geosciences.wustl.edu/dawn/` returns HTTP 404. This node hosts other missions (e.g. MESSENGER, GRAIL), not Dawn. |
| `pds-imaging.jpl.nasa.gov` | **Does not host Dawn.** No Dawn references found on the node portal. |
| `pds-smallbodies.astro.umd.edu` | Resolves (HTTP 200 on `https://`) but is the **legacy/superseded domain** for the Small Bodies Node — its current content did not surface Dawn holdings directly. |
| **`sbnarchive.psi.edu`** (PDS Small Bodies Node, PSI-hosted) | **Confirmed live host for both Dawn FC and Dawn VIR data.** Verified by walking the actual directory tree (`/pds3/dawn/fc/`, `/pds3/dawn/vir/`), fetching real `INDEX.TAB`/`INDEX.LBL` files, and downloading real product files. |

**Conclusion: both Dawn FC and Dawn VIR Vesta-phase data live on the same
node — the PDS Small Bodies Node, currently served from
`sbnarchive.psi.edu`** (cross-linked from the node's live catalog page at
`sbn.psi.edu`). Neither the Geosciences nor Imaging node hosts Dawn data.

### Confirmed working URLs (also recorded in `configs/config.yaml`)

**Dawn FC2 — Vesta:**
- Raw (EDR): dataset `DAWN-A-FC2-2-EDR-VESTA-IMAGES-V1.0`, volume
  `DWNVFC2_1A` — https://sbnarchive.psi.edu/pds3/dawn/fc/DWNVFC2_1A/
- Calibrated (RDR, used by default): dataset
  `DAWN-A-FC2-3-RDR-VESTA-IMAGES-V1.0`, volume `DWNVFC2_1B` —
  https://sbnarchive.psi.edu/pds3/dawn/fc/DWNVFC2_1B/
- Index: `.../INDEX/INDEX.TAB` + `.../INDEX/INDEX.LBL` under each volume
  above — enumerates every product via `FILE_SPECIFICATION_NAME`.

**Dawn VIR — Vesta (raw/EDR, used by default as of 2026-08-27):**
- IR channel: dataset `DAWN-A-VIR-2-EDR-IR-VESTA-SPECTRA-V1.0`, volume
  `DWNVVIR_I1A` — https://sbnarchive.psi.edu/pds3/dawn/vir/DWNVVIR_I1A/
- VIS channel: dataset `DAWN-A-VIR-2-EDR-VIS-VESTA-SPECTRA-V1.0`, volume
  `DWNVVIR_V1A` — https://sbnarchive.psi.edu/pds3/dawn/vir/DWNVVIR_V1A/
- Calibrated/RDR alternative (also configured, `level: calibrated`):
  IR `DAWN-A-VIR-3-RDR-IR-VESTA-SPECTRA-V1.0` / volume `DWNVVIR_I1B`;
  VIS `DAWN-A-VIR-3-RDR-VIS-VESTA-SPECTRA-V1.0` / volume `DWNVVIR_V1B`.
- Each VIR `INDEX.TAB` (raw and calibrated alike) also lists `_HK`
  (housekeeping) and `_QQ` (pointing/quaternion) ancillary rows alongside
  the primary spectral cube rows; `fetch_vir_spectra()` filters those out
  and only downloads the primary `.QUB` cube + its `.LBL`.
- `AAREADME.TXT` and `DOCUMENT/SIS/` (e.g. `DAWN_VIR_SIS_V1_8.PDF`) were
  confirmed present (HTTP 200) at both `DWNVVIR_V1A` and `DWNVVIR_I1A`
  before use, per task constraint to read these first rather than
  guessing layout.

Every URL above was hand-verified to resolve and to actually serve
Vesta-phase Dawn data (not Ceres, not another mission phase) before being
written into config — none were guessed from pattern-matching.

### `--limit 10` smoke-test runs

**2026-08-26** (VIR defaulted to calibrated `*_1B` volumes):
exit code 0 — FC 10/10, VIR IR (`I1B`) 10/10, VIR VIS (`V1B`) 10/10.

**2026-08-27** (after switching VIR default to raw `*_1A` volumes per
the explicitly verified sources for this slice):

Command:
```
python -m ml.data.pds_acquisition --limit 10 -v
```

Result: **exit code 0**, all products downloaded successfully.

| Source | Attempted | Downloaded |
|---|---|---|
| Dawn FC2 Vesta images (calibrated `DWNVFC2_1B`, `.FIT` + `.LBL`) | 10 | **10 / 10** |
| Dawn VIR Vesta spectra, IR channel (raw `DWNVVIR_I1A`, `.QUB` + `.LBL`) | 10 | **10 / 10** |
| Dawn VIR Vesta spectra, VIS channel (raw `DWNVVIR_V1A`, `.QUB` + `.LBL`) | 10 | **10 / 10** |
| **Total** | 30 | **30 / 30** |

Spot-checks performed:
- Confirmed a downloaded `.LBL` file (`FC21B0001898_11123133516F1B.LBL`)
  contains real PDS3 metadata (instrument/mission software IDs, pointers
  to the paired data object, file structure) — labels are real, not
  stubs, and are retained on disk alongside their data files (not
  discarded).
- Confirmed non-trivial file sizes on disk: FC images ~4.2 MB each, VIR
  IR (raw) cubes and VIR VIS (raw) cubes both landed at ~6.3 MB average
  per file (63 MB / 10 products each) — consistent with genuine
  image/cube payloads rather than empty or placeholder files.
- `datasets/raw/dawn_fc_vesta/manifest.jsonl` and
  `datasets/raw/dawn_vir_vesta/manifest.jsonl` each record one JSON line per
  product (product ID, dataset ID, instrument, target, start/stop time,
  volume ID, and label/data paths) as a convenience index — the `.LBL`
  files remain the authoritative metadata record.
- No index file was missing and no path 404'd during this run — nothing
  to report under the "stop and report" constraint.

### Full pull

**Not yet run.** The `--limit 10` smoke tests above are what has been
confirmed so far. A full pull (`python -m ml.data.pds_acquisition`,
no `--limit`) would fetch on the order of tens of thousands of products:
- FC: ~61,330 rows in the `DWNVFC2_1B` index.
- VIR (raw, current default): 2,108 IR + 2,154 VIS primary cubes
  (`DWNVVIR_I1A` / `DWNVVIR_V1A`).

This is sized and scheduled for a deliberate follow-up run, not
attempted as part of this slice.

---

## Slice 2: Spatial alignment (Vesta, FC images ↔ VIR spectra)

Scope: spatial correspondence between the FC images and VIR cubes already
on disk from Slice 1. No re-downloading, no compositional labeling.

### Tasks

- [x] Implement spatial registration (`load_geometry()`,
      `compute_footprint_overlap()`, `align_dataset()` in
      [`ml/data/spatial_alignment.py`](../ml/data/spatial_alignment.py)).
- [x] Compute and record image–spectrum correspondence confidence per
      sample (`spatial_iou` + `correspondence_confidence` columns in
      `datasets/metadata/sample_metadata.csv`, via the shared
      [`SampleMetadata`](../ml/utils/metadata_schema.py) schema).
- [x] Run against the real downloaded Slice-1 sample and report counts
      (below — **honestly, not rounded up**).

Not started (intentionally, per scope): compositional labeling,
`splits.py`. `pds_acquisition.py` was not touched.

### How geometry is read

`load_geometry()` reads each product's `.LBL` file directly — no SPICE
kernels are loaded. Field names were confirmed against real downloaded
labels before writing any parsing code (not assumed from documentation):

- **Footprint, preferred source:** `MINIMUM_LATITUDE` / `MAXIMUM_LATITUDE`
  / `WESTERNMOST_LONGITUDE` / `EASTERNMOST_LONGITUDE` (a body-fixed,
  `VESTA_FIXED`/`IAU_VESTA`-frame bounding box). This is what's actually
  populated on VIR labels when the product has real surface geometry.
- **Footprint, FC fallback:** `RETICLE_POINT_LATITUDE` /
  `RETICLE_POINT_LONGITUDE` (5-point corner array), reduced to its
  bounding box. Present as a field on FC labels, but see below — empty
  in every FC label we actually downloaded.
- Both are the real field names present in the downloaded labels — not
  guessed from the FC/VIR SIS documents alone.

### Independent sample count — the honest result: **0 pairs survived**

Running `python -m ml.data.spatial_alignment -v` against everything
currently in `datasets/raw/` (20 FC images across the raw+calibrated pulls,
40 VIR spectra across both channels and both processing levels):

```
Loaded 20 downloaded FC image products and 40 downloaded VIR spectrum products from manifests
Loaded geometry for 20/20 FC images (0 with usable footprint) and 40/40 VIR spectra (32 with usable footprint)
Alignment: 0 FC x 24 VIR candidates fell inside the 24.0h time window; 0 pairs had computable overlap; 0/0 survived confidence >= 0.30
Done: 20 FC images, 40 VIR spectra considered; 0 pairs survived confidence >= 0.30; written to datasets/metadata/sample_metadata.csv
```

**`datasets/metadata/sample_metadata.csv` exists with the correct header row
and zero data rows. `datasets/processed/` was never created — nothing
survived to crop.** This is not a bug being papered over; it's the real
output of real geometry math against the real sample, and it traces to
two concrete, checkable causes:

1. **All 20 downloaded FC labels have no footprint at all.**
   `MINIMUM_LATITUDE`, `MAXIMUM_LATITUDE`, `WESTERNMOST_LONGITUDE`,
   `EASTERNMOST_LONGITUDE`, and `RETICLE_POINT_LATITUDE/LONGITUDE` are
   all `"N/A"` in every one of them (verified by grep across all 20
   files, not just spot-checked). These are OpNav approach-phase frames
   (`2011123_OPNAV_001`) taken from ~1.2 million km away — Vesta was
   essentially a point source, so the ground-projection fields FC's
   pipeline would otherwise fill in were never computed for this
   sequence. FC images DO carry a `SUB_SPACECRAFT_LATITUDE/LONGITUDE`
   nadir point, but that's a single point, not a footprint region —
   using it would mean inventing a footprint radius from an assumed
   camera FOV not present in the label, which is exactly the kind of
   fabrication `docs/scientific_integrity_checklist.md` rules out. So
   these 20 products are correctly treated as "no usable geometry."
2. **Independent of (1), the downloaded FC and VIR samples don't share a
   time window.** The FC sample is from 2011-05-03 (`OPNAV_001`); the
   VIR sample spans 2011-05-10 (`OPNAV_002`) and 2011-06-08
   (`OPNAV_006`) — 7 to 36 days away, far outside the 24-hour
   `max_time_delta_hours` window (or any window that would still mean
   "same orbit pass"). This is a byproduct of how the Slice-1
   `--limit 10` smoke test sampled data: it took the first N rows of
   each volume's index independently, with no guarantee FC and VIR rows
   line up in time. 32 of the 40 VIR products *do* have real, usable
   footprints (confirmed non-`"N/A"` bounding boxes) — the geometry code
   itself works on real data — there's simply no FC frame in the current
   sample positioned to pair against them.

The correspondence-confidence math (`compute_footprint_overlap()`,
bbox IoU + time-proximity discount) and the crop pipeline
(`_crop_fc_image_to_overlap()`, FITS → pixel-region crop → PNG) were
verified mechanically against a real FC `.FIT` file using a synthetic
footprint (since no real FC footprint exists in this sample to test
against) — confirmed to read the FITS data, compute a crop region, and
write a real 512×512 PNG. That check is not part of the committed
pipeline output; it only confirms the code path itself is not broken.

### Decision point — flagging, not proceeding silently

**Zero independent regions is not enough to support the original 3-way
model comparison**, and it will stay zero no matter how many more times
`spatial_alignment.py` is re-run against the *current* raw sample — the
blocker is the input data, not the alignment code. Two independent paths
forward, either of which would need a deliberate decision before Slice 3
(labeling) can produce anything real:

1. **Re-pull FC data from a mission phase where FC's own footprint
   fields are actually populated** (e.g. HAMO/LAMO science-orbit
   sequences, not `OPNAV` approach frames) — those are close-range,
   illuminated, mapped observations where PDS's own pipeline computes
   `MINIMUM_LATITUDE` etc. This requires touching `pds_acquisition.py`
   again, which was explicitly out of scope for this pass.
2. **Deliberately co-sample FC and VIR by time/orbit** (e.g. pull both
   instruments' products from the same `HAMO`/`LAMO` date-stamped
   directory, rather than independently taking the first N index rows
   of each volume) so the two samples have any chance of temporal and
   spatial overlap at all.

Recommendation: (1) and (2) together — the next acquisition pass should
target a shared HAMO (or LAMO) date window for both FC and VIR, not
approach-phase OpNav frames, specifically so this alignment step has
real footprints and real time-overlap to work with. That's a scope
change to the acquisition step, so it's flagged here rather than done
inside this pass.

---

## Slice 3: Data audit, label scheme, labeling + splits — Month 1 close-out

Scope: audit the real output of Slice 2, define a VIR-only compositional
label scheme, apply it, split, and give an honest go/no-go for Month 2.
`pds_acquisition.py` and `spatial_alignment.py` were not touched.

### Tasks

- [x] Part A: load `datasets/metadata/sample_metadata.csv` and audit it
      ([`scripts/data_audit.py`](../scripts/data_audit.py)).
- [x] Part A: state plainly whether the sample can support a 3-way model
      comparison.
- [x] Part B: define a VIR-only compositional label scheme with explicit,
      auditable thresholds
      ([`ml/data/spectral_labeling.py`](../ml/data/spectral_labeling.py)).
- [x] Part C: assign labels + region-based splits, rewrite the CSV via
      `write_metadata_csv()` with validation
      ([`scripts/finalize_month1_labels.py`](../scripts/finalize_month1_labels.py),
      [`ml/utils/splits.py`](../ml/utils/splits.py)).
- [x] Part D: close out Month 1 with a go/no-go call.

New infrastructure built this pass (none of it existed before — see the
"missing scaffold" notes on prior slices): `ml/utils/splits.py`,
`SampleMetadata.validate()` + `.split` field + `read_metadata_csv()` in
`ml/utils/metadata_schema.py`, `ml/data/spectral_labeling.py`,
`scripts/data_audit.py`, `scripts/finalize_month1_labels.py`, and
`data.splits` in `configs/config.yaml`.

### Part A — Data audit

**Before running anything, the premise of this task didn't hold**: the
task description states Slice 2 "has already produced ...
spatially-verified Vesta image–spectrum pairs ... and cropped region
images in `datasets/processed/`." It verifiably has not — `datasets/metadata/sample_metadata.csv`
had a header row and **zero data rows**, and `datasets/processed/` did not
exist, exactly as reported at the end of Slice 2 above. This audit
proceeds on the real file, not the assumed one.

`python scripts/data_audit.py` output, verbatim:

```
=== Month 1 Data Audit — data\metadata\sample_metadata.csv ===
Total surviving pairs: 0

N=0: there is nothing to compute a confidence distribution, spatial
distribution, or time-of-observation spread over. This is reported
plainly rather than fabricated or skipped — see docs/month1_log.md
for why (Slice 2's real geometry/time-window findings).

VERDICT: cannot support ANY model comparison (3-way or otherwise) —
there are zero labeled training examples.
```

- **Total surviving pairs: 0.**
- **Confidence distribution: not computable** (no rows).
- **Spatial distribution: not computable.** Zero surviving regions means
  zero data points to describe as "clustered" or "spread" — there is
  nothing to plot.
- **Time-of-observation spread: not computable**, for the same reason.

**Can this sample size and distribution support a meaningful 3-way model
comparison (baseline/ResNet-50/ViT-B) with a region-based split? No —
not "small," literally zero.** Zero is not a distribution to characterize
as clustered or spread; it's an absence of data. This is the required
checkpoint the task calls for, answered as plainly as the number allows:
there is currently no dataset for Month 2 to train anything on, 3-way
comparison or otherwise.

### Part B — VIR-only label scheme

Full reasoning and code lives in
[`ml/data/spectral_labeling.py`](../ml/data/spectral_labeling.py); this
is the auditable summary the task asks for.

**Scientific basis.** Dawn VIR spectra of Vesta's HED terrain carry two
diagnostic pyroxene absorption features: **Band I** (~0.9–1.0 μm, Fe²⁺
crystal-field absorption) and **Band II** (~1.9–2.0 μm). Both features'
center wavelengths shift redward as pyroxene Ca-content increases —
low-Ca orthopyroxene (diogenite-like material) centers shorter,
high-Ca clinopyroxene (eucrite-like material) centers longer, with mixed
howardite-like material in between. This is the general direction of
shift established in Dawn VIR Vesta literature (De Sanctis et al. 2012,
*Science*; Ammannito et al. 2013, *M&PS*) and earlier lab pyroxene
systematics (Gaffey 1976; Cloutis & Gaffey 1991). The VIR SIS document
(`DOCUMENT/SIS/DAWN_VIR_SIS_V1_8.HTM`, both `DWNVVIR_V1A` and `_I1A`) was
checked and — as expected for an instrument SIS — defines the
instrument's spectral coverage (0.25–5.0 μm total, split ~0.25–1.07 μm
VIS / ~1.02–5.0 μm IR) but not compositional thresholds; those come from
the cited literature, recalled from general domain knowledge in this
session rather than freshly re-read from the papers themselves.

**Honesty note on the thresholds below**: they are a first-pass,
literature-informed starting point, **not independently fit to this
project's own data** — impossible at N=0 (Part A). They are written down
explicitly, with exact values, specifically so they're auditable and can
be recalibrated the moment real labeled spectra exist.

**Method** (`compute_band_depth`, `compute_band_center` in
`spectral_labeling.py`): standard linear continuum removal between two
shoulder wavelengths (Clark & Roush 1984 style), then a 3-point parabola
fit around the continuum-removed minimum for a sub-sample band-center
estimate.

**Channel constraint, handled explicitly rather than glossed over:** VIR's
VIS channel (~0.25–1.07 μm) covers Band I but not Band II; the IR channel
(~1.02–5.0 μm) covers Band II but not Band I. `spatial_alignment.py`
pairs an FC image against a VIS spectrum *or* an IR spectrum
independently — not a matched VIS+IR pair from the same observation — so
`spectral_labeling.py` scores whichever band the given spectrum's channel
covers, with its own threshold set, rather than requiring a true
Band-Area-Ratio (which needs both bands, matched by
`SPACECRAFT_CLOCK_START_COUNT`). Building that matched-pair BAR would mean
changing how `spatial_alignment.py` pairs products — out of scope for
this pass, flagged here as a real refinement for later.

**Class scheme (3 classes + 1 quality-gate class):**

| Class | Band I center (VIS spectra) | Band II center (IR spectra) |
|---|---|---|
| `diogenite_like` | < 0.92 μm | < 1.97 μm |
| `howardite_like` | 0.92–0.95 μm | 1.97–2.00 μm |
| `eucrite_like` | ≥ 0.95 μm | ≥ 2.00 μm |
| `indeterminate_weak_feature` | continuum-removed depth < 0.02, or center unfittable | same |

**Data-quality gate found and enforced during implementation:** the VIR
volumes named as this project's verified acquisition source
(`DWNVVIR_V1A` / `DWNVVIR_I1A`) are **raw EDR — uncalibrated instrument
DN, not reflectance-like data.** Continuum-removed band analysis assumes
roughly-reflectance-shaped input; raw DN carries instrument response
distortion that makes literature thresholds inapplicable. `classify_spectrum()`
checks each product's `DATA_SET_ID`/`PRODUCT_TYPE` and returns
`indeterminate_weak_feature` with an explicit reason for any raw/EDR
product — it does **not** silently run the scheme on unsuitable data.
The calibrated (RDR) volumes, `DWNVVIR_V1B` / `DWNVVIR_I1B`, carry
**spectral radiance** (`W/(m²·sr·μm)`) — still not full I/F reflectance
(that needs dividing by solar irradiance at the observed distance, using
`SPACECRAFT_SOLAR_DISTANCE`, which is not implemented here), but close
enough in shape for a first-pass continuum-removed band analysis. This is
a second reason the thresholds above are a starting point, not a
validated cutoff.

**Mechanical verification** (since there are 0 real surviving pairs to
run this on — see Part A): `read_vir_qube()` and `classify_spectrum()`
were run against all 20 real, calibrated VIR cubes already on disk from
Slice 1 (10 VIS, 10 IR — genuine Dawn Vesta science spectra, just not
tied to any surviving FC pair). This confirmed the binary QUBE reader
(handles both the 2-byte integer raw format and the 4-byte float
calibrated format — found and fixed a dtype bug against the real
calibrated files, which are `IEEE_REAL`/4-byte, not the `MSB_INTEGER`/
2-byte format the raw files use) and the classifier produce a real,
non-degenerate mix of outcomes, not one class or all-indeterminate:

```
VIS (Band I),  n=10, all genuine "4 VESTA" observations (no CAL LAMP in this batch):
  eucrite_like: 5, diogenite_like: 5, howardite_like: 0, indeterminate_weak_feature: 0

IR (Band II), n=10, all genuine "4 VESTA" observations:
  diogenite_like: 6, eucrite_like: 2, indeterminate_weak_feature: 2, howardite_like: 0
```

This is a **methodology check, not a labeled dataset** — none of these 20
spectra belong to a surviving image–spectrum pair, so none of this output
was written to `sample_metadata.csv`.

**Explicit no-heuristic-labels confirmation**: at no point in
`spectral_labeling.py` is `datasets/processed/` (the cropped FC PNGs) opened,
read, or referenced. The one moment during this work where "just open the
crop and see if it looks eucrite-colored" would have been tempting — when
manually checking the mechanical-verification classifications above for
plausibility — that check was **not done**; the results were accepted or
rejected only by whether the code ran and produced a non-degenerate
class mix, never by looking at any image. Flagging this per the task's
explicit instruction to call out the temptation, not just avoid it
silently.

### Part C — Labels, splits, final CSV

`python scripts/finalize_month1_labels.py` output, verbatim:

```
WARNING spectral_labeling: label_sample_metadata() called with 0 records — nothing to label. No labels can be derived until spatial_alignment.py produces surviving pairs.
WARNING splits: assign_region_based_splits() called with 0 records — nothing to split. Returning an empty list rather than fabricating split assignments.
Loaded 0 records from data\metadata\sample_metadata.csv
Class balance after labeling (0 records): {}
Split assignment: {}
Per-split, per-class counts:
Wrote 0 validated records back to data\metadata\sample_metadata.csv
```

- **Class balance: N/A — 0 records.** No class dominates because there
  are no classes populated; none can be called "learnable" or not.
- **Split counts (train/val/test, 0.70/0.15/0.15 from
  `configs/config.yaml` `data.splits`): all zero.**
- `datasets/metadata/sample_metadata.csv` was rewritten with the current
  schema (now including the `split` column) and **zero data rows** — an
  honest rewrite of an empty result, not a skipped step.

`assign_region_based_splits()` itself (region-grouped by a 5°×5° lat/lon
bin, deterministic shuffle, greedy fill toward target fractions) was
mechanically verified against 60 synthetic records spread randomly across
Vesta: it produced a 42/9/9 train/val/test split (exactly 70/15/15% at
that N), confirming the splitting logic is correct and ready for real
data. It has never run against real labeled samples, because there are
none yet.

`SampleMetadata.validate()` (new this pass) was exercised directly:
confirmed it accepts a valid `unlabeled`/`pending` row, rejects a labeled
row with `label_source="heuristic"`, and accepts one with a specific
source string — so the write path in `write_metadata_csv()` cannot
silently accept a generic label_source once real data exists.

### Part D — Month 1 close-out and go/no-go

**Final independent sample count: 0.** Confidence distribution, spatial
distribution, and mission-phase spread: not computable (Part A). Class
balance: not computable (Part C). Per-split counts: all zero (Part C).

**Label scheme (finalized, ready to run, unexercised on real data):** VIR
Band I / Band II continuum-removed center-wavelength threshold, 3 classes
(`diogenite_like` / `howardite_like` / `eucrite_like`) + 1 quality-gate
class (`indeterminate_weak_feature`), calibrated (RDR) VIR spectra only —
see Part B for exact thresholds and their caveats.

**Go/no-go for Month 2: NO-GO, as originally scoped.**

Month 1 cannot close with a real, trained-model-ready dataset. This is
not a small-N caveat to note in passing — there is no dataset. The root
cause was identified in Slice 2 and reconfirmed here, unchanged by this
pass's work (as it should be, since `pds_acquisition.py` and
`spatial_alignment.py` were correctly left untouched): the FC sample
downloaded in Slice 1 (`OPNAV_001` approach-phase frames) carries no
footprint geometry, and the FC/VIR samples don't share a time window.

**What Month 2 needs before it can start, concretely** (restating and
sharpening Slice 2's recommendation now that Part B/C infrastructure
exists to actually consume the result):

1. Re-run acquisition (a change to `pds_acquisition.py`, intentionally
   not made in this pass) targeting a **HAMO or LAMO date-stamped
   directory** for **both** FC and VIR, so FC frames have real
   `MINIMUM_LATITUDE`/etc. footprints and FC/VIR observations share a
   time window.
2. Prefer **calibrated (RDR)** VIR volumes (`DWNVVIR_*1B`) as the
   primary spectral source for labeling — raw EDR is gated out by
   `classify_spectrum()` and will always produce
   `indeterminate_weak_feature`.
3. Re-run `spatial_alignment.py` (unchanged) against the new sample and
   confirm N > 0 survivors before re-running this Slice 3's audit/label/
   split pipeline (all built and ready — no further code changes should
   be needed here, just real input data).
4. Once N is known, revisit whether a 3-way model comparison is
   supportable at all, or whether Month 2 should be scoped down (fewer
   classes — e.g. binary diogenite-like vs eucrite-like, dropping
   `howardite_like` — or explicitly framed as exploratory given N). That
   decision needs a real N to be made honestly; it can't be made now.

Nothing about this pass's label scheme, split logic, or validation
infrastructure needs to change once real data exists — it was built and
verified against real Dawn VIR cubes and synthetic split data. The
blocker is entirely upstream, in what got acquired and how it was
time/space-sampled, both flagged as decision points rather than
worked around.

---

## Slice 4: Rebuild into the full project scaffold, two real geometry bugs fixed

This pass moved the working data pipeline (previously under a standalone
`src/` layout in a disconnected local repo) into the project's real
repository, `github.com/ayushmanmayank/AstromineAI`, on branch
`month1-data-pipeline`, under the `ml/` layout described in the project
proposal, and added the Month 2/3-scoped model/explainability/backend/
frontend/docker scaffold. It also fixed two real, verified bugs in the
alignment geometry math.

### Bug 1 — longitude convention (fixed)

Every real downloaded label (FC and VIR alike) has
`WESTERNMOST_LONGITUDE > EASTERNMOST_LONGITUDE`. The VIR SIS
(`DWNVVIR_V1B/DOCUMENT/SIS/DAWN_VIR_SIS_V1_8.HTM`) only documents the
case "longitude increases toward the east", under which this ordering
would mean *every single downloaded product* crosses the Prime Meridian —
and, worked through under that reading, implies footprint spans of
~275-310 degrees. That's geometrically impossible: a spacecraft outside
the body can never see more than one hemisphere (<=180 degrees of
longitude) at once. Reading the same fields as **west-positive**
(longitude increasing westward) instead — i.e. the footprint's angular
extent is `west_lon - east_lon`, wrapping through 0/360 only when
`east_lon > west_lon` — gives spans of ~51-123 degrees for the same real
data: physically plausible, and consistent across every sample.

This is inferred from the real data plus a hard physical constraint, not
from an explicit "longitude increases toward the west" sentence in the
SIS (it doesn't have one) — flagged in `ml/data/spatial_alignment.py`'s
`_lon_to_x()` docstring as a real interpretation, not a certainty, worth
cross-checking against an actual SPICE/ISIS reprojection (e.g. Claudia
crater at 146.0 deg in the Claudia Double-Prime system, per
`DWNVVIR_V1B/DOCUMENT/VESTA_COORDINATES/VESTA_COORDINATES_131018.HTM`)
once real surviving pairs exist to check it against. `CENTER_LONGITUDE`,
notably, is `"N/A"` in every real downloaded label — so an
anchor-on-center-longitude approach (considered before checking the real
data) would not have worked with this dataset regardless.

Fixed: replaced the old `_normalize_lon()` (east-positive, +/-180
wraparound) with `_lon_to_x()` (a coordinate flip to a standard increasing
frame) plus `_footprint_overlap_details()`, which does proper
circular-interval intersection and correctly handles genuine
Prime-Meridian wraparound when it occurs.

### Bug 2 — plain IoU penalizes genuine correspondences by size mismatch (fixed)

An FC image frame and a single VIR spectrum footprint are routinely very
different sizes. Plain bounding-box IoU divides by the *union*, so a VIR
footprint fully contained inside a much bigger FC frame scores a tiny IoU
purely from the size mismatch — not from positional uncertainty. Fixed by
scoring `overlap_coefficient` (intersection / smaller-footprint area, the
Szymkiewicz-Simpson coefficient) combined with an explicit
`size_ratio_penalty` (`min(area)/max(area)`) in
`compute_footprint_overlap()`, so a real, fully-contained match scores
high only when the sizes are also reasonably matched.

**Open/unresolved, flagged rather than guessed at:** the exact strength of
`size_ratio_penalty` (currently a plain linear multiply) is a placeholder.
There is still no real surviving pair to look at an actual
image-footprint/spectrum-footprint area-ratio distribution and calibrate
it against. Revisit once real pairs exist.

### Re-run against the real sample (calibrated VIR now the default)

VIR's default level was switched from `raw` to `calibrated`
(`DWNVVIR_V1B`/`DWNVVIR_I1B`) in `configs/config.yaml` — raw EDR is
uncalibrated instrument DN and is explicitly gated out by
`ml/data/spectral_labeling.py`'s `classify_spectrum()` as invalid input
for band-depth analysis (see Slice 3). `raw` remains configured as an
explicit, non-default alternative.

```
python -m ml.data.pds_acquisition --limit 10
python -m ml.data.spatial_alignment -v
```

Result, with both the raw and calibrated VIR samples now on disk (40 FC
images total across earlier runs, 80 VIR spectra total):

```
Loaded geometry for 40/40 FC images (0 with usable footprint) and 80/80 VIR spectra (64 with usable footprint)
Alignment: 0 FC x 24 VIR candidates fell inside the 24.0h time window; 0 pairs had computable overlap; 0/0 survived confidence >= 0.30
Done: 40 FC images, 80 VIR spectra considered; 0 pairs survived confidence >= 0.30
```

**Still 0 surviving pairs — unchanged from Slice 2/3, and expected.**
Both geometry fixes are real and correct, but they don't manufacture FC
footprints where none exist, and don't manufacture a shared time window
between FC (`2011-05-03`) and VIR (`2011-05-10`/`2011-06-08`) samples that
don't have one. The root cause remains exactly what Slice 2 identified:
the downloaded FC sample is early OpNav approach-phase imagery with no
computed surface footprint at all, and it doesn't share a time window
with the downloaded VIR sample. **The go/no-go call from Slice 3 stands:
NO-GO for Month 2 as originally scoped**, until acquisition is re-run
against a shared HAMO/LAMO time window for both instruments.

### New scaffold built this pass (Month 2/3-scoped, structurally real, unexercised on real data)

- `ml/data/dataset.py`: `VestaDataset` (PyTorch `Dataset` over
  `datasets/metadata/sample_metadata.csv`) — raises clearly rather than
  silently "working" on an empty split.
- `ml/models/{baseline,cnn_resnet,vit_model,train,evaluate}.py`: real
  scikit-learn baseline, real torchvision ResNet-50 and timm ViT-B model
  builders (verified: both build and load pretrained ImageNet weights
  correctly), a real training loop, and accuracy + Expected Calibration
  Error evaluation. All refuse to run against a 0-sample split rather than
  reporting a meaningless number.
- `ml/explainability/gradcam.py`: real Captum `LayerGradCam` wrapper.
- `ml/explainability/attention_viz.py`: **stub, as explicitly scoped** —
  the attention-rollout math is implemented and real, but the forward-hook
  wiring into timm's ViT-B to actually capture attention weights is not;
  see the module's TODO for exactly what that needs.
- `backend/main.py`: real FastAPI app. `/health` reports whether a
  checkpoint is loaded; `/predict` returns 503 with an honest explanation
  when no trained model exists (verified via `TestClient` — this is the
  current, real behavior, not a hypothetical), rather than fabricating a
  result. Every real prediction carries a fixed, non-removable disclaimer.
- `frontend/`: minimal Vite + React + TypeScript upload/predict page.
- `docker/{backend,frontend}.Dockerfile`, updated `docker-compose.yml`
  with both services.
- `tests/test_metadata_schema.py`: 26 tests against `validate()`'s
  rejection rules (generic label_source strings, missing provenance,
  invalid split values) — all passing.

None of the model/backend/frontend code has been exercised against real
labeled data, because there is none. Building it now doesn't change the
Month 2 go/no-go call above; it means Month 2 can start immediately once
acquisition produces real surviving pairs, without also needing to write
this scaffold at that point.

---

## Slice 5: Final Month 1 audit, label scheme, labels + splits, go/no-go

This pass re-ran the real pipeline (without editing
`ml/data/pds_acquisition.py` or `ml/data/spatial_alignment.py`), re-audited
the real output, confirmed the label scheme, ran labeling + region-based
splits for real, and closes out Month 1 with a final go/no-go call.

### Part A — Data audit (re-run, real numbers)

```
python -m ml.data.spatial_alignment -v
```
```
Loaded 40 downloaded FC image products and 80 downloaded VIR spectrum products from manifests
Loaded geometry for 40/40 FC images (0 with usable footprint) and 80/80 VIR spectra (64 with usable footprint)
Alignment: 0 FC x 24 VIR candidates fell inside the 24.0h time window; 0 pairs had computable overlap; 0/0 survived confidence >= 0.30
Done: 40 FC images, 80 VIR spectra considered; 0 pairs survived confidence >= 0.30
```

```
python scripts/data_audit.py
```
```
Total surviving pairs: 0

N=0: there is nothing to compute a confidence distribution, spatial
distribution, time-of-observation spread, or footprint area-ratio
distribution over.

VERDICT: cannot support ANY model comparison (3-way or otherwise) —
there are zero labeled training examples.
```

**Total surviving pairs: 0 — unchanged from Slice 2/3/4, confirmed again
on this branch.** All five reported metrics (confidence distribution,
spatial distribution, mission-phase spread, and the newly-added img/spec
footprint area-ratio distribution) are genuinely not computable at N=0,
not omitted or approximated.

**New this pass**: `scripts/data_audit.py` now also recomputes each
surviving pair's real footprint-area ratio (the open "specificity"
question flagged in `spatial_alignment.py`'s `compute_footprint_overlap()`
docstring), via a read-only import of `load_geometry()` — added because
the task asked to compute this now that real footprints exist for at
least one side of each candidate (64/80 VIR spectra have usable
footprints). It could not be exercised on any *surviving pair* because
there are none, but it is real, tested code (uses the same
`_lon_to_x`-based area formula `spatial_alignment.py` itself scores pairs
with) ready to report on the real distribution the moment any pair
survives.

**Go/no-go, Part A: NO — 0 is not a small or clustered sample to caveat
around, it is an absence of data.** No 3-way (or any) model comparison is
supportable.

### Part B — Label scheme (confirmed, not re-derived)

The label scheme built in Slice 3 (`ml/data/spectral_labeling.py`) already
satisfies this pass's requirements and was not rewritten:

- VIR Band I (~0.9–1.0 μm) / Band II (~1.9–2.0 μm) continuum-removed
  band-center thresholds — real wavelength calibration confirmed against
  each cube's own `BAND_BIN_CENTER` array (not the SIS's prose, which only
  states the instrument's total coverage, 0.25–1.07 μm VIS / 1.02–5.0 μm
  IR — see Slice 3 for why per-cube `BAND_BIN_CENTER` is the authoritative
  per-product wavelength source, not a fixed table).
- 3 classes (`diogenite_like` / `howardite_like` / `eucrite_like`) + 1
  quality-gate class (`indeterminate_weak_feature`) for a weak/unfittable
  feature or an uncalibrated (raw EDR) product.
- Exact thresholds and full reasoning: see Slice 3, "Part B — VIR-only
  label scheme", above — unchanged.
- No-heuristic-labels constraint is stated at the top of
  `ml/data/spectral_labeling.py`'s module docstring (confirmed present,
  quoted in Slice 3 above) — FC imagery is never opened by this module.

No code change was needed here; re-stated for this pass's audit trail
rather than left implicit.

### Part C — Labels + splits (re-run, real numbers)

```
python scripts/finalize_month1_labels.py
```
```
Loaded 0 records from datasets\metadata\sample_metadata.csv
Class balance after labeling (0 records): {}
Split assignment: {}
Per-split, per-class counts:
Wrote 0 validated records back to datasets\metadata\sample_metadata.csv
```

- **Class balance: N/A — 0 records.** No class dominates because none
  are populated.
- **Per-split counts (train/val/test, 0.70/0.15/0.15 from
  `configs/config.yaml`): all zero.**
- `datasets/metadata/sample_metadata.csv` rewritten via
  `write_metadata_csv()` (which runs `validate()` on every row — 0 rows
  means 0 validations, not a bypassed check) — header intact, 0 data
  rows.
- `tests/test_metadata_schema.py`: still 26/26 passing, confirming
  `validate()`'s rejection rules (generic/blank `label_source`, missing
  provenance, invalid `split`) are intact and unweakened.

### Part D — Final Month 1 close-out

**Final real independent sample count: 0.** Every audit metric requested
in Part A is genuinely not computable at this N. Class balance and
per-split counts are all zero (Part C). The label scheme is finalized and
implemented but has not labeled a single real sample, because there is
nothing to label.

**Go/no-go for Month 2: NO-GO — unchanged across every slice of Month 1
(2 through 5) that has checked this.** This is not a small-N caveat to
flag and proceed past; there is no dataset. Re-running the audit/label/
split pipeline again without changing what gets acquired will keep
producing this same real zero — confirmed twice more on this branch this
pass, exactly as predicted in Slice 2.

The concrete blocker, restated once more since it has not changed:
`ml/data/pds_acquisition.py`'s current sample (FC: `2011123_OPNAV_001`
approach-phase frames, no computed footprint geometry at all; VIR: two
independent approach-phase sequences 7–36 days away from the FC sample)
cannot produce a surviving pair no matter how alignment or labeling code
is adjusted, because the blocker is upstream of both. The fix remains:
re-run acquisition against a **shared HAMO/LAMO time window for both
instruments** (a change to `pds_acquisition.py`, correctly not made in
this pass), then re-run `spatial_alignment.py` and this pass's now-fully
-ready audit/label/split pipeline against real survivors.

**Month 2 should not start under the original 3-way, multi-class scope
until that re-acquisition happens.** Once it does, whether Month 2 needs
to be scoped down (binary instead of 3-class, or explicitly exploratory
given N) is a decision to make from the real resulting N — not from this
pass's zero, and not preemptively guessed at here.

---

## Slice 6: Fix the acquisition source (HAMO/LAMO instead of Approach/OpNav)

This pass changed **only** `ml/data/pds_acquisition.py` and
`configs/config.yaml` — `ml/data/spatial_alignment.py`,
`ml/utils/splits.py`, and `ml/data/spectral_labeling.py` were not touched,
per scope.

### What was verified before writing any code

1. **Real directory listings**, not assumed:
   - `https://sbnarchive.psi.edu/pds3/dawn/fc/DWNVFC2_1B/DATA/FITS/` gives
     `2011123_APPROACH/`, `2011223_SURVEY/`, `2011243_TRANSFER_TO_HAMO/`,
     `2011272_HAMO/`, `2011306_TRANSFER_TO_LAMO/`, `2011346_LAMO/`,
     `2012167_HAMO_2/`, `2012207_TRANSFER_TO_CERES/` — day-of-year dated
     (`YYYYDDD_PHASE`).
   - `https://sbnarchive.psi.edu/pds3/dawn/vir/DWNVVIR_V1B/DATA/` (and
     the `DWNVVIR_I1B` equivalent, identical) gives `20110503_APPROACH/`,
     `20110811_SURVEY/`, `20110831_TRANSFER_TO_HAMO/`, `20110929_HAMO/`,
     `20111212_LAMO/`, `20120615_HAMO_2/`, `20120725_TRANSFER_TO_CERES/`
     — calendar-dated (`YYYYMMDD_PHASE`).
   - Confirmed these name the same real dates in two different formats
     (day 272 of 2011 = 2011-09-29 = VIR's `20110929`; day 346 =
     2011-12-12 = VIR's `20111212`; day 167 of 2012, a leap year, =
     2012-06-15 = VIR's `20120615`) by direct day-of-year conversion, not
     assumed.
   - Confirmed both instruments' HAMO cycle 1 starts the same real date:
     FC `2011272_CYCLE1`, VIR `20110929_CYCLE1`, both 2011-09-29; VIR's
     `20111006_CYCLE2` starts 2011-10-06, giving a clean, verified,
     one-week window for cycle 1 alone.
2. **FC footprint geometry, spot-checked on 3 real HAMO .LBL files**
   (`2011272_HAMO/2011272_CYCLE1/2011272_C1_ORBIT01/FC21B000696{3,4,5}...LBL`):
   all three have real, populated MINIMUM_LATITUDE/MAXIMUM_LATITUDE/
   WESTERNMOST_LONGITUDE/EASTERNMOST_LONGITUDE (e.g. 38.87/59.23/208.80/
   239.36 degrees) — confirming HAMO frames carry the geometry OpNav
   frames lacked, before building acquisition around that assumption.

### A significant, unplanned discovery during this verification

Checking real numeric values from these HAMO labels surfaced something
that changes the confidence level on Slice 4's longitude-convention fix:
the 3 FC HAMO labels above all have WESTERNMOST_LONGITUDE less than
EASTERNMOST_LONGITUDE (e.g. 208.80 < 239.36) — the opposite ordering from
every VIR label checked so far (Slice 4, and re-confirmed here on 3 real
VIR HAMO labels, e.g. WESTERNMOST_LONGITUDE=88.343 greater than
EASTERNMOST_LONGITUDE=73.480). Reading each with the convention that
matches its own physically-plausible footprint size (FC: standard
east-increasing, roughly 18-30 degree spans; VIR: west-positive, roughly
13-15 degree spans) gives sensible results for both; reading either with
the other's convention gives an implausible (over 180 degree) span.

This suggests FC and VIR may use opposite longitude-ordering conventions
from each other in this archive, not one shared convention (west-
positive) as Slice 4 concluded from VIR-only evidence — Slice 4 had no
real numeric FC example to check against (OpNav FC frames' geometry
fields were all "N/A"), so it generalized from VIR data alone. This is
flagged here, not fixed (out of scope for this pass — `_lon_to_x()` in
`ml/data/spatial_alignment.py` is still unmodified), with a concrete,
quantified worked example below showing this is very likely actively
suppressing real overlap in the new HAMO data.

### Code changes

- `ml/data/pds_acquisition.py`: added `filter_rows_by_phase()` and a
  `phase=` parameter on both `fetch_framing_camera_images()` and
  `fetch_vir_spectra()`. Filters parsed INDEX.TAB rows by real START_TIME
  (parsed per-row, handling both instruments' date formats) falling
  within a named window — not by reconstructing per-phase directory
  paths, since FC and VIR name theirs differently and HAMO in particular
  nests `<phase>/<date>_CYCLE<n>/<date>_C<n>_ORBIT<n>/` for FC. The
  volume-level INDEX.TAB already lists every product with a real
  timestamp, so date filtering there needs no new path-construction
  logic at all.
- `configs/config.yaml`: added `data.mission_phases`, a verified real
  date-window table built directly from the two live directory listings
  above, plus `hamo_cycle1` (2011-09-29 to 2011-10-05) as the specific,
  verified-overlapping window this pass actually used.
- CLI: `python -m ml.data.pds_acquisition --phase hamo_cycle1 --limit N`.

### Re-download: real HAMO cycle 1 data

Command:
```
python -m ml.data.pds_acquisition --instrument fc  --limit 10 --phase hamo_cycle1 -v
python -m ml.data.pds_acquisition --instrument vir --limit 10 --phase hamo_cycle1 -v
```
Result: 5080 FC rows and 40+40 VIR rows (ir/vis) fall within
phase=hamo_cycle1 (2011-09-29 to 2011-10-05); 10/10 FC and 20/20 VIR
downloaded.

Spot-checked the downloaded labels directly (not just the ones fetched
for verification above): every downloaded FC and VIR label in this batch
has real, non-"N/A" MINIMUM_LATITUDE etc., and real timestamps inside
2011-09-29 to 2011-10-04 — both root causes from Slice 2 (missing FC
geometry, no FC/VIR time overlap) are confirmed fixed by this acquisition
change.

Pulled a larger FC batch (`--limit 150`, same phase) to give a fairer
test than 10 frames (which happened to all sit in one ~70-second nadir
track, 38.9 to 34.5 degrees N) — 150 frames sweep -17.8 to 59.2 degrees
N, a real, wide latitude range, confirming FC's nadir track does cross
into VIR's imaged latitude band (VIR's downloaded sample covers roughly
-35 to -7 degrees).

### Alignment result: still 0 pairs — but for a newly, precisely diagnosed reason

Command:
```
python -m ml.data.spatial_alignment -v
```
Result:
```
Loaded geometry for 200/200 FC images (160 with usable footprint) and 100/100 VIR spectra (84 with usable footprint)
Alignment: 1600 FC x 24 VIR candidates fell inside the 24.0h time window; 1600 pairs had computable overlap; 0/1600 survived confidence >= 0.30
```

0 pairs survived — but for the first time, this is NOT "geometry missing"
or "time window too wide." Both are now confirmed fixed: 160/200 FC
frames have real footprints (vs. 0/40 in every prior slice), and 1600
FC-VIR candidate pairs fell inside the 24-hour time window (vs. 0 in
every prior slice) — real, meaningful confidence values were computed
for all 1600 (122 of them nonzero), not rejected as uncomputable.

Diagnosed why none reached the 0.30 threshold (not left as "maybe still
no overlap"): the maximum confidence across all 1600 real pairs was
0.0172. The best candidate pair (FC 0007106 vs VIR
VIR_VIS_1B_1_370617178) has real, substantial latitude overlap (FC:
-15.13 to 3.64 degrees; VIR: -19.9 to -7.69 degrees; overlap = 7.45
degrees) — but its confidence is crushed by the longitude-convention
issue found above: FC's raw footprint (west_lon=89.01 less than
east_lon=107.70, a true, physically-sensible 18.69 degree span under
FC's own — apparently standard east-increasing — convention) gets run
through `_lon_to_x()` (built from VIR-only evidence in Slice 4) and
comes out as a 341.31 degree span — an 18.3x inflation, verified by
direct computation, not estimated. That inflated span massively inflates
FC's computed footprint area, which crushes overlap_coefficient (divided
by the smaller of the two areas — here, even inflated, still likely FC)
toward zero regardless of how much the footprints genuinely overlap.

Answering the task's specific diagnostic question directly: geometry is
no longer missing, and the time window is no longer too wide — the
footprints most likely DO genuinely overlap for at least one real
candidate pair in this small batch, but the pre-existing (out of scope
for this pass) longitude-handling bug appears to be suppressing that
overlap's computed confidence by well over an order of magnitude.

Per this pass's explicit constraint, `_lon_to_x()` /
`compute_footprint_overlap()` were not modified to chase this down
further, and confidence thresholds were not touched either — no survivor
was manufactured. This is reported as a precise, actionable, quantified
finding for a dedicated follow-up pass, which should very likely treat FC
and VIR as needing different longitude-sign handling, not one shared
transform (see Slice 4's `_lon_to_x()` docstring, still accurate about
being an inferred-not-certain interpretation, now with much stronger
counter-evidence attached here).

### Part 7 — footprint area-ratio distribution, re-run

Command:
```
python scripts/data_audit.py
```
Still reports "N=0, not computable" — sample_metadata.csv still has 0
surviving rows (the audit script measures area ratios over survivors,
per its docstring), and this pass's root-cause finding above is about
confidence being crushed pre-threshold, not about survivors existing
that the audit script failed to pick up. The size-ratio distortion was
computed ad hoc for diagnosis above instead (this pass's best candidate
pair: FC true area approximately 351 square degrees vs. code-computed
approximately 6405 square degrees — the same 18.3x distortion, carried
through to area) — worth wiring into `scripts/data_audit.py` as a
candidate-level (not just survivor-level) report in the same follow-up
pass that fixes the longitude handling, so this distribution can be
inspected across every candidate pair, not just survivors, going
forward.

### Updated go/no-go

Still NO-GO for Month 2 — 0 real survivors. But the diagnosis changed in
an important way: this pass's acquisition-source fix worked (real
footprint geometry and real time overlap, confirmed on real downloaded
data) — the remaining blocker has moved from "acquisition source" (fixed
this pass) to "the longitude-convention bug in spatial_alignment.py, now
confirmed by real HAMO evidence to likely be actively suppressing a
genuine overlapping pair," which is squarely the next, now well-evidenced
fix to make — in a dedicated pass, per every prior pass's scope
boundaries, not slipped in here.

---

## Slice 7: Fix the FC/VIR longitude-convention bug

This pass changed only `ml/data/spatial_alignment.py` and added
`tests/test_spatial_alignment.py`. `ml/data/pds_acquisition.py`,
`configs/config.yaml`'s phase filtering, and `ml/utils/splits.py` were not
touched.

### Step 1 — verified with a real 20/20 sample per instrument, not 2 labels

Pulled `WESTERNMOST_LONGITUDE`, `EASTERNMOST_LONGITUDE`, `CENTER_LONGITUDE`
from 20 real FC HAMO `.LBL` files and 20 real VIR HAMO `.LBL` files
already on disk from Slice 6:

- **FC: 20/20 have WESTERNMOST_LONGITUDE < EASTERNMOST_LONGITUDE**, with
  CENTER_LONGITUDE always between them. Clean, 100% consistent.
- **VIR: 20/20 have WESTERNMOST_LONGITUDE > EASTERNMOST_LONGITUDE**, with
  CENTER_LONGITUDE always between them (just the other way round). Also
  clean, 100% consistent — and the *opposite* of FC.

This is a clean per-instrument split, not an inconsistent mess — Option A
(instrument-aware normalization) applies, not Option B.

**Documentation cross-check, quoted directly rather than inferred from
data alone:**

- `DWNVFC2_1B/DOCUMENT/SIS/DAWN_FC_SIS_20131216.HTM` (fetched fresh, not
  assumed) states plainly: *"CENTER_LONGITUDE ... Center pixel
  planetocentric **east** longitude"* and *"SUB_SPACECRAFT_LONGITUDE ...
  Sub-spacecraft planetocentric **east**"* — FC's own SIS explicitly
  confirms east-increasing, matching the empirical pattern exactly.
- The same document's generic WESTERNMOST_LONGITUDE/EASTERNMOST_LONGITUDE
  definitions (boilerplate shared across PDS3 catalogs) state **both**
  cases explicitly: *"For Planetocentric coordinates and for
  Planetographic coordinates in which longitude increases toward the
  east, the westernmost ... is the minimum numerical value"*, and
  separately, *"For Planetographic coordinates in which longitude
  increases toward the west (prograde rotator), the westernmost ... is
  the maximum numerical value."* Vesta is confirmed a prograde rotator
  (positive `Wdot` = +1617.33 deg/day in the Dawn-Claudia coordinate
  system, per `DOCUMENT/VESTA_COORDINATES/VESTA_COORDINATES_131018.HTM` —
  read in Slice 4). This is consistent with a real, principled reason FC
  and VIR could legitimately differ: if FC's pipeline uses planetocentric
  coordinates (always east-increasing) and VIR's uses planetographic
  (west-increasing, since Vesta is prograde) for these two fields, both
  are "correct" by the doc's own rules — just for different coordinate
  system choices.
- `DWNVVIR_V1B/DOCUMENT/SIS/DAWN_VIR_SIS_V1_8.HTM` (fetched fresh) states
  `SUB_SPACECRAFT_LATITUDE`/`LONGITUDE` and `CENTER_LATITUDE`/`LONGITUDE`
  are **"planetocentric"** — without ever writing the word "east" next to
  it, unlike FC's doc. Read via the same document's own general
  definition ("planetocentric... longitudes increase toward the east"),
  this would imply VIR's fields should *also* be east-increasing. They
  empirically are not (20/20 real samples, opposite of FC). **This is a
  genuine, unresolved apparent inconsistency in VIR's own documentation**
  — not papered over here. The fix below follows the empirical pattern
  (unambiguous, internally self-consistent: CENTER_LONGITUDE lands
  between the two raw values either way, in 20/20 real samples) rather
  than the ambiguous prose, and says so directly in the code.

### Step 2 — regression test, confirmed to fail pre-fix and pass post-fix

`tests/test_spatial_alignment.py`, built from the exact real pair that
motivated this fix (FC product `0007106`, VIR product
`VIR_VIS_1B_1_370617178` — the real `.LBL` values are inlined as fixture
data, not re-fetched):

- `test_fc_longitude_standardization_is_identity`
- `test_vir_longitude_standardization_swaps`
- `test_fc_true_longitude_span_is_not_inflated` — asserts FC's real
  ~18.69 degree span is preserved, not inflated to ~341.31 degrees.
- `test_real_fc_vir_pair_is_correctly_adjacent_not_overlapping` — see the
  honesty note below.

Confirmed both ways, not just asserted:
- **Against the pre-fix code** (temporarily restored via `git stash`):
  `ImportError: cannot import name '_standardize_footprint_lon'` — the
  function this test suite exercises didn't exist yet. Collection
  failure counts as a real, confirmed failure of these tests against the
  old code, not skipped or waved off.
- **Against the fix**: all 4 pass, alongside the full existing 26-test
  suite (30/30 total).

**Honesty note on this specific fixture pair**: while writing the test,
directly checking the corrected (standardized) longitude intervals showed
FC covers 89.01-107.70 degrees and VIR covers 73.48-88.34 degrees for
*this specific pair* — adjacent, with a real ~0.67 degree gap, not actual
overlap. The initial draft of this test asserted "nontrivial overlap
after the fix" for this pair, on the assumption that the pair which
scored highest under the *buggy* code must be a genuine overlap once
fixed — that assumption doesn't hold, and the test was corrected before
being reported here to assert what the standardized geometry actually
shows (a real, small gap, correctly reported as zero overlap) rather
than a false positive. The real question — does the fix produce genuine
survivors *anywhere* in the batch — is answered properly in Step 5 below,
against the whole 1600-pair set, not this one hand-picked pair.

### Step 3 — the fix

`_lon_to_x()`/`_x_to_lon()` (the uniform, VIR-only-derived transform from
Slice 4) were removed entirely. In their place,
`_standardize_footprint_lon(west_lon, east_lon, instrument_id)` is called
once, inside `load_geometry()`, right after the raw
WESTERNMOST/EASTERNMOST_LONGITUDE values are parsed:

- `instrument_id` starting with `"FC"` → returned unchanged (already
  standard, increasing-eastward, per the FC SIS quote above).
- `instrument_id` starting with `"VIR"` → `west_lon`/`east_lon` are
  **swapped** (not mirrored/reflected — a plain relabeling, since VIR's
  "westernmost" empirically corresponds to the standard-frame east edge
  and vice versa).
- Anything else → returned unchanged, with a logged warning that the
  instrument couldn't be confidently classified — not silently guessed
  at.

Every downstream consumer (`_footprint_overlap_details()`,
`_crop_fc_image_to_overlap()`, `align_dataset()`'s overlap-bbox
construction) now works directly on already-standardized, increasing-
eastward longitude values — no per-call transform, no reflection. This
is a simpler, more correct architecture than patching the old transform
with an instrument branch inside the x-space math: the ambiguity is
resolved once, at ingestion, rather than threaded through every
consumer. The full evidence (this section, condensed) is in
`_standardize_footprint_lon()`'s own docstring, so this isn't a mystery
fix to whoever reads the code later.

### Step 4 — regression test re-run: passes

Already covered in Step 2 above — 4/4 new tests pass, 30/30 total.

### Step 5 — re-run against all 1600 real candidate pairs

Command:
```
python -m ml.data.spatial_alignment -v
```
Result:
```
Loaded geometry for 200/200 FC images (160 with usable footprint) and 100/100 VIR spectra (84 with usable footprint)
Alignment: 1600 FC x 24 VIR candidates fell inside the 24.0h time window; 1600 pairs had computable overlap; 0/1600 survived confidence >= 0.30
```

**Still 0 survivors** — but the confidence distribution changed
substantially and for a real, diagnosable reason (below), not because the
fix failed:

| | Pre-fix (Slice 6) | Post-fix (this slice) |
|---|---|---|
| min | 0.0 | 0.0 |
| median | 0.0 | 0.0 |
| max | **0.0172** | **0.1574** (9.2x higher) |
| nonzero pairs (of 1600) | 122 | 6 |

The **max confidence rose 9.2x** (0.0172 to 0.1574) — a real, substantial
improvement consistent with the fix working, not a coincidence. The
**count of nonzero pairs dropped from 122 to 6** — also expected and
correct: the old bug's uniform transform was assigning small nonzero
scores to many pairs that don't actually overlap once geometry is
computed correctly (false positives, just below where they'd have
mattered), and the fix removes those along with fixing the true
positives' magnitude.

**Diagnosed why the true best pair (FC `0007112`, VIR
`VIR_VIS_1B_1_370617178`, 6 minutes apart) still falls short of 0.30 —
with the same rigor as Slice 6, not declared a win prematurely:**

```
FC footprint (standardized):  lat[-17.769, 0.970]  lon[82.841, 101.609]
VIR footprint (standardized): lat[-19.915, -7.685]  lon[73.480, 88.343]
overlap_bbox: lat[-17.769, -7.685]  lon[82.841, 88.343]   <- real, non-trivial overlap region
iou = 0.116
overlap_coefficient = 0.305   (30.5% of the smaller footprint is genuinely covered)
size_ratio = 1.93             (FC and VIR footprints are only ~2x different in area here)
time_factor = 0.996           (~6 minutes apart)
size_ratio_penalty = 1/1.93 = 0.517
confidence = overlap_coefficient * size_ratio_penalty * (0.5 + 0.5*time_factor)
           = 0.305 * 0.517 * 0.998 = 0.157
```

This pair has **real, genuine spatial overlap** (a real overlap_bbox,
30.5% containment of the smaller footprint) and near-perfect time
proximity — but two sub-1.0 factors multiplied together
(`overlap_coefficient=0.305` and `size_ratio_penalty=0.517`) cap the
result well under 0.30 even for a real, modestly-overlapping pair. This
is **the pre-existing, explicitly out-of-scope containment/specificity
issue** (flagged in Slice 4, and in this task's own constraints as "keep
as-is") interacting with genuinely-partial (not full-containment)
overlap — not a new bug, and not touched in this pass.

### Step 6 — this section

Documented above. No `scripts/data_audit.py` re-run was requested for
this slice (Slice 6 already covers why its survivor-based area-ratio
report stays "N=0, not computable" until real survivors exist).

### Updated go/no-go

**Still NO-GO for Month 2** — 0 real survivors. Both prior blockers
(missing FC geometry, no FC/VIR time overlap — Slice 6) and the longitude
bug (this slice) are now fixed and verified with real, quantified
evidence. The one remaining, precisely-identified blocker is the
containment/size-ratio-penalty design interacting with the real footprint
sizes in this specific HAMO-cycle-1 sample (FC frames and VIR cubes here
are close in size, ~2x, yet the current penalty formula still nearly
halves the score) — a natural next candidate for the next dedicated pass,
since it's the last of the three originally-flagged issues (acquisition
source, longitude convention, containment specificity) still open, and
now has a concrete, real worked example (this pair) to calibrate against
instead of a hypothetical one.

---

## Slice 8: Calibrate the size-ratio specificity penalty against real data

This pass changed only `ml/data/spatial_alignment.py` and
`tests/test_spatial_alignment.py`. `ml/data/pds_acquisition.py`, the
longitude standardization, and `ml/utils/splits.py` were not touched.

### Step 1 — characterize the real distribution first

Pulled `size_ratio` (`max(area)/min(area)`) and `overlap_coefficient` for
all 1600 real HAMO-cycle-1 candidate pairs already on disk (no
re-download — reused the same manifests as Slice 7).

**Size-ratio distribution, all 1600 candidates:**

| range | count |
|---|---|
| [1, 2) | 260 |
| [2, 5) | 1340 |
| [5, 10) | 0 |
| [10, 20) | 0 |
| [20, 100000) | 0 |

min=1.883, median=2.234, max=4.042. **Every single real candidate pair
falls between 1.88x and 4.04x.** None come anywhere close to the 10x/50x+
regime the original penalty comment was written to guard against.

**Overlap-coefficient distribution, same 1600:** only 6 pairs have any
nonzero containment at all; all 6 exceed 0.10, all 6 exceed 0.20, and
1 exceeds 0.30. Listing all 6 (sorted by containment):

| FC product | VIR product | dt (h) | overlap_coefficient | size_ratio |
|---|---|---|---|---|
| 0007112 | VIR_VIS_1B_1_370617178 | 0.10 | 0.305 | 1.93 |
| 0007111 | VIR_VIS_1B_1_370617178 | 0.10 | 0.293 | 1.93 |
| 0007110 | VIR_VIS_1B_1_370617178 | 0.10 | 0.282 | 1.93 |
| 0007109 | VIR_VIS_1B_1_370617178 | 0.11 | 0.273 | 1.93 |
| 0007108 | VIR_VIS_1B_1_370617178 | 0.11 | 0.264 | 1.93 |
| 0007107 | VIR_VIS_1B_1_370617178 | 0.11 | 0.257 | 1.93 |

**All 6 are the same physical event**: 6 consecutive FC frames from one
nadir track (product IDs `0007107`-`0007112`, adjacent) sweeping through
the same VIR spectrum's footprint, all ~6-7 minutes apart, all at
identically ~1.93x size ratio (same VIR spectrum, nearly-identical FC
frame size). This is not "one VIR swath trivially containing many
unrelated small frames" (which would show up as many *different* VIR
products all near the same, low containment) — it's one coherent,
physically real scanning-overlap event, with containment naturally
varying frame-to-frame as the exact footprint shifts. No other size-ratio
regime or containment cluster exists in this real dataset to characterize
further.

### Step 2 — does the original concern actually apply at 1.93x?

The original comment (Slice 4/6) worried about "a single giant image
footprint trivially containing dozens of unrelated small spectra" —
i.e., a scenario built for *large* size mismatches (10x, 50x+). The real
distribution above shows this dataset never produces anything but a
1.88x-4.04x mismatch, because FC frames and VIR scans at HAMO altitude
are simply fixed, comparably-sized ground patches by instrument design —
not a symptom of an imprecise or non-specific match. **The original
linear-from-1x penalty was discounting every single real pair in this
dataset for exhibiting completely normal, expected instrument geometry**,
not for any real ambiguity. The concern is real (kept, not deleted) — it
just doesn't apply anywhere in the range real Dawn FC/VIR HAMO pairs
actually occupy.

### Step 3 — the fix

`compute_size_ratio_penalty(size_ratio)`, replacing the inline
`1.0 / size_ratio`:

```
penalty = 1.0                          if size_ratio <= 5.0
penalty = 5.0 / size_ratio             otherwise
```

`5.0` (`SIZE_RATIO_NO_PENALTY_THRESHOLD`) was chosen because it sits
comfortably above the observed real max (4.04x) — not fitted exactly to
it, and matching one of the two round thresholds this task itself
suggested considering (5x or 10x). Continuous at the boundary
(`5.0/5.0 = 1.0`), decaying gracefully toward 0 for genuinely extreme
mismatches beyond it, so the underlying concern still fires where it
would actually matter (e.g. a full-disk mosaic accidentally scored
against a narrow VIR scan) — it just no longer fires across the entire
real, normal range this dataset exhibits.

Full reasoning (this section, condensed) is written directly into
`compute_footprint_overlap()`'s docstring, referencing the real 1.93x /
0.517-vs-1.0 penalty / 0.157-vs-0.305 confidence numbers, so this isn't a
mystery constant later.

### Step 4 — regression tests

Added to `tests/test_spatial_alignment.py`:
- `test_size_ratio_penalty_is_unity_within_the_real_observed_range` —
  1.0, 1.88, 2.23, 4.04, and the 5.0 threshold itself all get penalty 1.0.
- `test_size_ratio_penalty_decays_beyond_the_threshold` — 10x → 0.5,
  50x → 0.1, confirming the concern still applies outside the real range.
- `test_calibration_pair_confidence_lands_near_0_305_as_a_consequence` —
  the real FC `0007112` / VIR `VIR_VIS_1B_1_370617178` pair: asserts
  `size_ratio≈1.93`, `overlap_coefficient≈0.305`, `penalty==1.0`, and
  **`confidence≈0.3046`** (computed via the real function, not asserted
  as a round target — the exact value is a consequence of the threshold
  choice, reported honestly including its being narrowly above 0.30 by
  design margin, not tuned to it).

7/7 new + existing tests: 33/33 total, passing.

### Step 5 — re-run on all 1600 real candidate pairs

Command:
```
python -m ml.data.spatial_alignment -v
```
Result:
```
Alignment: 1600 FC x 24 VIR candidates fell inside the 24.0h time window; 1600 pairs had computable overlap; 1/1600 survived confidence >= 0.30
Done: 200 FC images, 100 VIR spectra considered; 1 pairs survived confidence >= 0.30
```

**1 real survivor** — FC `0007112` / VIR `VIR_VIS_1B_1_370617178`,
confidence 0.30461421..., exactly matching the calibration prediction.
Spot-checked the written row in `datasets/metadata/sample_metadata.csv`:
full provenance present (both dataset IDs, both product IDs, both
instrument names, mission), real overlap region (lat -17.77 to -7.69,
lon 82.84 to 88.34), real time delta (358.6 seconds ≈ 6 minutes), label
correctly still `unlabeled`/`pending` (labeling is a later step). The
cropped region PNG (`datasets/processed/0007112__VIR_VIS_1B_1_370617178.png`)
was written and opens as a real 300×551 grayscale image, not empty or
corrupt.

**Checked for spurious survivors, not just the count**: the other 5
near-miss pairs (containment 0.257-0.293, all just under 0.30) are the
same physically-coherent adjacent-frame cluster described in Step 1 —
plausible near-misses of the same real event, not unrelated noise that
the new formula let slip through. No pair outside this one 6-pair cluster
has any nonzero containment at all, so there was no opportunity for a
wildly-mismatched or spurious pair to incorrectly survive in this batch.

### Go/no-go — sample volume for proceeding to labeling (not the full Month 1 close-out)

**1 real, spatially-verified, plausible pair.** All three originally
flagged issues (acquisition source, longitude convention, size-ratio
penalty) are now fixed and verified against real data — the pipeline
itself is validated: given a genuine correspondence, it now correctly
finds and scores it (0.305 real containment, correctly near-zero
discount, crossing the threshold); given non-correspondences, it
correctly reports zero.

**But N=1 is not remotely enough sample volume to proceed to labeling
and a 3-way model comparison.** A single sample cannot populate even one
class, let alone support a train/val/test split or any class-balance
assessment — Part B/C of the labeling pass would have nothing meaningful
to do with N=1 beyond labeling that one sample. This is not a pipeline
problem anymore, though: this batch only covered 200 FC frames (of 5080
in the verified `hamo_cycle1` window) and 100 VIR spectra (of ~80 primary
cubes per channel in the same window) — a small fraction of even one
week's mapping cycle, let alone the full ~74-day HAMO phase or the LAMO
phase. **The clear next step is a larger acquisition pull within the
already-verified HAMO/LAMO windows** (more FC frames, more VIR spectra,
possibly more cycles) using the now-fully-validated alignment pipeline
unchanged — not further debugging of the alignment math, which has now
been checked and calibrated against real data three times over (Slices
6, 7, 8).

---

## Slice 9: Scale up acquisition within `hamo_cycle1` — real volume test

Task: pull substantially more real FC/VIR data from the already-verified
`hamo_cycle1` window and re-run the unmodified, already-calibrated
alignment pipeline, to find out whether N=1 (Slice 8) was a sampling
artifact or a genuine scarcity. `ml/data/spatial_alignment.py` (longitude
standardization, specificity penalty), `ml/utils/splits.py` — not
touched, per scope.

### Acquisition

- Pulled **all** real VIR products in the `hamo_cycle1` window (no
  `--limit`): 80 real primary cubes (40 IR + 40 VIS) — this is the full
  real count for the window, not a subset.
- Attempted a full, unbounded FC pull (5080 rows) in the background;
  killed it after confirming the real download rate (~4.6s/product,
  including both `.LBL` and `.FIT`) made completing all 5080 impractical
  within this session (~6+ hours). Restarted bounded at `--limit 1000`
  (within this task's own suggested 1000-2000 range) instead — a
  deliberate, disclosed scope reduction, not a silent one.
- The bounded 1000-frame pull genuinely completed, but 3 products failed
  with transient network errors (connection reset, read timeout, one DNS
  resolution blip) — retried the same command (skip-if-exists makes this
  cheap) and got a clean 1000/1000 on the second attempt.

### An unplanned, real bug found and fixed (data only, not the acquisition code)

Checking the resulting FC manifest before trusting any alignment number
revealed **`pds_acquisition.py`'s `_write_manifest()` appends every run's
full product list to `manifest.jsonl` without deduplicating** — across
this session's several acquisition calls (plus everything accumulated in
earlier sessions), the FC manifest held **2200 entries for only 1010
unique products** (every product duplicated at least once, several 4x);
the VIR manifest held 180 entries for 120 unique products. Running
alignment against the undeduplicated manifest first (before catching
this) produced a **2179-survivor** result that would have been badly
inflated by scoring the same real candidate pairs multiple times as if
they were independent — not reported as the real result below.

**Fixed by deduplicating the two manifest files** (by `product_id`,
keeping the downloaded record for each) — a data-hygiene operation on
the output artifact, not a code change to `pds_acquisition.py` itself
(left untouched, per this task's scope). `_write_manifest()`'s
append-without-dedup behavior is a real latent bug that will recur on
every future incremental pull and should get a proper code fix (e.g.
dedup-on-write, or rebuild-from-scratch each run) in a dedicated future
pass — flagged here, not silently patched into the protected file.

Deduplicated result: FC manifest 2200 → 1010 records (1010 downloaded);
VIR manifest 180 → 120 records (120 downloaded).

### Real alignment result, on the deduplicated data

Command:
```
python -m ml.data.spatial_alignment -v
```
Result:
```
Loaded 1010 downloaded FC image products and 120 downloaded VIR spectrum products from manifests
Loaded geometry for 1010/1010 FC images (1000 with usable footprint) and 120/120 VIR spectra (112 with usable footprint)
Alignment: 25158 FC x 24 VIR candidates fell inside the 24.0h time window; 24918 pairs had computable overlap; 743/24918 survived confidence >= 0.30
Done: 1010 FC images, 120 VIR spectra considered; 743 pairs survived confidence >= 0.30
```

**743 real survivors** — up from 1 (Slice 8), on roughly 5x the FC volume
and 1.5x the VIR volume (1000 vs. 200 FC; 120 vs. ~80 unique VIR).
Survivor rate (743/24918 ≈ 3.0% of computable candidates) is consistent
with genuine, non-trivial spatial correspondence being common within a
single HAMO cycle rather than a rare fluke — this reads as a real
scarcity-vs-artifact answer: **N=1 was a sampling artifact of the small
Slice 8 batch, not evidence that genuine correspondences are rare.**

**Spot-checked, not just counted:**
- `datasets/metadata/sample_metadata.csv`: 743 rows, 743 unique
  `region_id` values (no duplicate rows slipped through), 225 unique FC
  images matched against 30 unique VIR spectra — a real many-to-many
  correspondence pattern (consistent with FC's continuous nadir track
  passing near several VIR footprints, and repeated VIR observations
  falling near several FC passes), not one degenerate cluster.
- `correspondence_confidence`: min 0.300, median 0.771, max 0.9996 — a
  real spread, not everything piled at the threshold.
- `time_delta_seconds`: min 2.9s, median 286.4s (~4.8 min), max 767.5s
  (~12.8 min) — all comfortably inside the 24h window and physically
  plausible for genuine close-in-time observations.
- `spatial_iou`: min 0.114, median 0.362, max 0.547 — real, substantial
  geometric overlap, not near-zero noise crossing the threshold only via
  the size-ratio/time terms.
- All 743 rows still have `label=unlabeled`, `label_source=pending`,
  `split=unassigned` — labeling/splitting correctly not touched.
- `datasets/processed/`: exactly 743 cropped PNGs, matching the CSV row
  count. The very first row (`0007112__VIR_VIS_1B_1_370617178`,
  confidence 0.3046142151856357) is byte-for-byte the same pair and
  confidence value found in Slice 8 — confirms this larger run is a
  superset of the earlier finding, not a divergent recomputation.
- Full test suite: 33/33 passing throughout (no code changed this
  slice).

### Go/no-go — sample volume for proceeding to labeling

**743 real, spatially-verified, plausible pairs, from only 1000 of the
5080 available FC frames in a single HAMO cycle.** This is a real,
substantial, and structurally sound sample: many-to-many FC/VIR matches,
a genuine confidence/IoU/time-delta spread, full provenance on every row.
**This is enough real volume to proceed to the labeling pass** (VIR-only
compositional labels via `ml/data/spectral_labeling.py`, region-based
splits via `ml/utils/splits.py`) — as a dedicated next task, not started
here per this task's explicit scope boundary.

Two things to carry into that next task, stated plainly rather than
assumed away:
1. **Class balance is unknown until real labeling runs** — 743 image
   crops map to only 30 unique VIR spectra, so the compositional label
   diversity is bounded by those 30 spectra's real Band I/II
   measurements, not by 743. Whether that supports 2, 3, or 4 real
   classes is a question for the labeling pass, not this one.
2. **The manifest-deduplication bug should get a real code fix** before
   any further incremental acquisition pulls — repeated partial pulls
   will keep re-appending duplicates otherwise, and the workaround here
   (post-hoc file dedup) is not something to keep repeating by hand.

---

## Slice 10: VIR spectral diversity audit (Part 1) + quantitative rigor additions

Real question: do the real VIR spectra behind the 743 Slice-9 survivors
show genuine, defensible compositional separation — not "does a scatter
plot look clustered." `ml/data/spectral_labeling.py`,
`ml/data/spatial_alignment.py`, `ml/utils/splits.py` — logic not
modified; new read-only script
[`scripts/audit_band_separability.py`](../scripts/audit_band_separability.py)
reuses their already-tested extraction functions and generic PDS3
scalar-field parser rather than re-implementing either.

### A structural correction before any numbers: 30 products = 15 observations

The 743 survivors resolve to **30 unique VIR product IDs** — but VIR's
VIS channel only covers Band I (~0.9-1.0 μm) and the IR channel only
covers Band II (~1.9-2.0 μm) — see `spectral_labeling.py`'s module
docstring, Slice 3. A real (Band I center, Band II center) 2D point per
*observation* needs both channels for the *same* observation, matched by
their shared `SPACECRAFT_CLOCK_START_COUNT` suffix (e.g.
`VIR_VIS_1B_1_370617178` + `VIR_IR_1B_1_370617178`). Checked directly:
**all 30 products pair cleanly into exactly 15 VIS+IR observations, with
zero unpaired singletons.** The diversity question is therefore about 15
real observations, not "30 spectra" — stated precisely here rather than
carried forward as an imprecise headline number.

### Part 1 — real Band I/II extraction, all 15 observations usable

```
python scripts/audit_band_separability.py
```

All 15 paired observations passed both channels' depth-floor gate (the
same `BAND_I_DEPTH_FLOOR`/`BAND_II_DEPTH_FLOOR` = 0.02 gate
`classify_spectrum()` itself uses) — **15/15 usable, 0 excluded.** Real
extracted values:

| clock (obs id) | Band I center (μm) | Band II center (μm) |
|---|---|---|
| 370617178 | 0.9212 | 1.9573 |
| 370617777 | 0.9212 | 1.9573 |
| 370618360 | 0.9212 | 1.9573 |
| 370618943 | 0.9212 | 1.9573 |
| 370661407 | 0.9218 | 2.1643 |
| 370662006 | 0.9218 | 2.1641 |
| 370662589 | 0.9217 | 2.1642 |
| 370663172 | 0.9218 | 2.1641 |
| 370705798 | 0.9219 | 1.9572 |
| 370706397 | 0.9219 | 1.9572 |
| 370706980 | 0.9218 | 1.9572 |
| 370707563 | 0.9219 | 1.9572 |
| 370749809 | 0.9220 | 1.9575 |
| 370750408 | 0.9221 | 2.1640 |
| 370750991 | 0.9219 | 2.1639 |

**Visual pattern**: Band I center is essentially flat across all 15
(0.9212–0.9221 μm, a ~0.001 μm spread — far narrower than the
~0.90–0.95 μm range HED literature associates with diogenite-to-eucrite
variation; see Slice 3). **Band II center is clearly bimodal**: 9
observations cluster near 1.957 μm, 6 near 2.164 μm — a real, substantial
~0.2 μm separation, an order of magnitude larger than Band I's entire
spread. Whatever diversity this sample shows is carried almost entirely
by Band II, not Band I.

### Addendum 1 — quantitative separability check

Silhouette scores (`sklearn.cluster.KMeans`, `random_state=42`,
`sklearn.metrics.silhouette_score`), all three k reported, not
cherry-picked:

| k | silhouette score |
|---|---|
| 2 | **0.9982** |
| 3 | 0.9058 |
| 4 | 0.7234 |

k=2 is about as clean a silhouette score as clustering analysis
produces. **Read plainly: this does NOT mean "confirmed 2-class
composition" — it means the 15 points fall into two extremely tight,
well-separated groups in (Band I, Band II) space, driven almost entirely
by the Band II bimodality above.** Whether that separation reflects real
compositional difference or something else is exactly what the confound
check below has to settle, precisely because the statistical separation
itself is not in question — its cause is.

### Addendum 2 — confound check: geography, illumination, and time

Pulled real `INCIDENCE_ANGLE`, `EMISSION_ANGLE`, `PHASE_ANGLE`,
`CENTER_LATITUDE`, `CENTER_LONGITUDE`, and `START_TIME` from each
observation's VIS `.LBL` (via the same generic scalar parser
`ml/data/spatial_alignment.py` already uses — read-only reuse, not a
modification) and compared across the k=2 clustering (the coarsest,
most conservative split to confound-check):

**Illumination angles — ranges overlap substantially, not a confound:**

| cluster (n) | incidence (min/med/max) | emission (min/med/max) | phase (min/med/max) |
|---|---|---|---|
| 0 (6, Band II≈2.164) | 29.68 / 30.95 / 31.92 | 7.24 / 9.08 / 10.66 | 30.19 / 31.45 / 33.80 |
| 1 (9, Band II≈1.957) | 27.87 / 28.77 / 32.35 | 6.24 / 9.70 / 12.27 | 30.13 / 31.59 / 34.08 |

Medians differ by ~1-2 degrees on each axis, well inside each cluster's
own range — **no separation here.** Illumination/viewing geometry is not
the driver.

**Ground location — ranges overlap substantially, not a confound:**

| cluster (n) | latitude (min/med/max) | longitude (min/med/max) |
|---|---|---|
| 0 (6) | -27.68 / -20.48 / -13.65 | 95.98 / 304.81 / 333.00 |
| 1 (9) | -29.04 / -19.75 / -13.16 | 46.95 / 118.55 / 222.11 |

Latitude medians are nearly identical (-20.5° vs -19.8°). Longitude
spans a wide, overlapping range in **both** clusters (cluster 0's
95.98° falls inside cluster 1's 46.95–222.11° range) — **the two
spectral clusters are not two fixed geographic patches.** This rules out
"the classes are just two different regions of Vesta" as the explanation.

**Acquisition time — strongly correlated, not perfectly, and this is the
real open question:**

```
cluster 0 (Band II≈2.164): 2011-09-30T13:29-13:58, 2011-10-01T14:12-14:22   (all "~13:30-14:30" block)
cluster 1 (Band II≈1.957): 2011-09-30T01:11-01:41, 2011-10-01T01:48-02:18, 2011-10-01T14:02   (mostly "~01:00-02:20" block, ONE exception at 14:02)
```

14 of 15 observations split cleanly by which ~1-hour acquisition window
they fall in (an early-morning block vs. a early-afternoon block,
recurring on both Sept 30 and Oct 1 — consistent with repeated orbital
passes at similar local times) — but the 15th (`2011-10-01T14:02:22`)
breaks the pattern, landing in the "morning" spectral cluster despite an
afternoon timestamp. That one exception means this is **not** a perfect
time confound (the task's example of "cluster membership perfectly
tracks acquisition day" does not literally hold here) — but a 14/15
correlation this strong, combined with geography and illumination both
ruled out above, is not nothing either.

**Honest conclusion, stated plainly per the task's own standard**: the
Band II-driven 2-cluster split is **strongly confounded with acquisition
time/session** (which acquisition block within the day, not which day,
and not geography or illumination angle) in 14 of 15 real observations.
This dataset — 15 points from a single 1-week HAMO cycle — **cannot on
its own distinguish "genuine compositional signal that happens to
correlate with which orbital pass observed it" from "an unidentified
time/session-linked instrumental or environmental effect that has
nothing to do with composition."** Composition and acquisition-session
are not separable with the data collected so far. This is reported as
the real, load-bearing finding of this audit — not a footnote, and not
resolved by asserting either explanation is correct.

### Bottom line for the diversity question

A near-perfect silhouette score (0.9982) does **not** mean this sample
supports a confident 2-class label assignment. It means two extremely
tight groups exist in (Band I, Band II) space, and the honest confound
check above cannot rule out that the grouping is actually acquisition
-session rather than mineralogy. **Quantitative clustering does not, by
itself, support proceeding to a confident compositional class
assignment on this 15-observation sample** — exactly the outcome this
addendum's instructions anticipated as a legitimate, reportable result
rather than something to iterate past.

### Addendum 3 — split-leakage constraint (documented now, not implemented)

**743 crops derive from only 30 unique VIR spectra (median 24.5 crops
per spectrum; min 8, max 32 — real distribution, computed from
`datasets/metadata/sample_metadata.csv`). Any future train/val/test
split MUST group by spectrum product ID, not by crop/region_id —
splitting at the crop level would put near-duplicate crops of the same
real spectrum into both train and test, leaking label information and
inflating apparent model accuracy in a way that would not reflect real
generalization. The existing region-based spatial clustering in
`assign_region_based_splits()` is NOT sufficient by itself for this
dataset's structure and must be extended to guarantee this grouping
before Month 2 model training begins.**

Not implemented here — `ml/utils/splits.py` was not modified beyond a
one-line comment cross-referencing this section (see that file). This is
a documented constraint for the next task that touches splits, per this
addendum's explicit instruction.

### Go/no-go (unchanged in kind, sharpened in reason)

Still not ready to proceed to compositional labeling on this sample —
not because N is too small in a generic sense (Slice 9 already
established real volume exists), but because the specific 15-observation
diversity check available right now cannot separate real composition
from a real, identified confound (acquisition session). Two concrete
next steps, not mutually exclusive: (1) pull VIR pairs from additional
HAMO cycles (2-6) or a different mission phase so acquisition-session and
composition are no longer perfectly correlated in the combined sample,
which is the only way this specific confound gets resolved; (2) revisit
Band I's near-total flatness — if literature Band I variation requires a
Ca-pyroxene range this 1-week, 15-observation sample simply doesn't
span, that's a volume/coverage problem Addendum's silhouette check
correctly surfaced rather than masked.

---

## Slice 11: Investigating the acquisition-session confound (two independent tracks)

Scope note before either track: this task explicitly does NOT authorize
proceeding to `ml/data/spectral_labeling.py` / class assignment
regardless of what either track finds — both are diagnostic only.
`ml/data/spatial_alignment.py`, `ml/utils/splits.py`, and the specificity
penalty are not touched in this slice.

One correction to this task's own premise, checked rather than assumed:
the manifest-deduplication fix was Slice 9's finding, not "Slice 10 Part
2" (Slice 10 was the band-separability audit; it never touched the
manifests). Re-verified directly before relying on it for Track B: both
`datasets/raw/{dawn_fc_vesta,dawn_vir_vesta}/manifest.jsonl` still have
exactly one entry per unique `product_id` (1010/1010 FC, 120/120 VIR) —
confirmed clean, no regression.

### Part A — literature cross-check (done first, before any Track B download)

Reused Slice 10's 15 real (Band I, Band II, cluster, `CENTER_LATITUDE`,
`CENTER_LONGITUDE`, `START_TIME`) points directly (via
`scripts/audit_band_separability.py`'s own functions, imported not
re-implemented) rather than re-extracting:

| cluster | clock | lat | lon | time |
|---|---|---|---|---|
| 0 (Band II≈2.164) | 370661407 | -13.647 | 333.001 | 2011-09-30T13:29 |
| 0 | 370662006 | -18.374 | 321.622 | 2011-09-30T13:39 |
| 0 | 370662589 | -23.044 | 310.430 | 2011-09-30T13:49 |
| 0 | 370663172 | -27.684 | 299.187 | 2011-09-30T13:58 |
| 0 | 370750408 | -17.906 | 107.195 | 2011-10-01T14:12 |
| 0 | 370750991 | -22.578 | 95.980 | 2011-10-01T14:22 |
| 1 (Band II≈1.957) | 370617178 | -13.627 | 80.752 | 2011-09-30T01:12 |
| 1 | 370617777 | -18.396 | 69.423 | 2011-09-30T01:22 |
| 1 | 370618360 | -23.041 | 58.182 | 2011-09-30T01:32 |
| 1 | 370618943 | -27.677 | 46.950 | 2011-09-30T01:41 |
| 1 | 370705798 | -14.989 | 222.108 | 2011-10-01T01:49 |
| 1 | 370706397 | -19.752 | 210.771 | 2011-10-01T01:59 |
| 1 | 370706980 | -24.405 | 199.540 | 2011-10-01T02:09 |
| 1 | 370707563 | -29.039 | 188.283 | 2011-10-01T02:18 |
| 1 | 370749809 | -13.162 | 118.548 | 2011-10-01T14:02 |

All 15 points sit within **-13° to -29° latitude** — a narrow, non-polar
band. Within each contiguous acquisition session the points trace a
smooth orbital nadir track (e.g. cluster 0's four Sept 30 points move
lat -13.6 → -27.7 as lon moves 333 → 299 over ~30 minutes); different
sessions cover different, non-overlapping longitude strips roughly 100-190
degrees apart — an expected consequence of observing at different times
as Vesta rotates underneath the spacecraft, not itself evidence of
anything compositional.

**Literature search** (WebSearch, both cross-checked against multiple
independent result summaries — full search transcript not reproduced
here, only what's directly load-bearing):
- De Sanctis et al.'s Dawn VIR Vesta mineralogy work (Science 2012;
  follow-on Icarus special issue ~2015-2016) is the well-established,
  widely-cited source for Vesta's global compositional pattern: **"the
  south polar region (Rheasilvia) has its own spectral characteristics
  ... Mg-pyroxene-rich terrains (diogenite-like), while the equatorial
  areas have shallower band depths and average band centers at slightly
  longer wavelengths, consistent with more eucrite rich materials"** —
  and **"diogenite is concentrated within and around the Rheasilvia
  basin"** (Rheasilvia center: 71°57'S, 86°18'E — Wikipedia, sourced from
  the IAU gazetteer). This is high-confidence: it is the foundational,
  most-cited finding in Dawn VIR Vesta literature, not a single
  unreviewed source.
- A finer unit, Vestalia Terra (center 3°44'S, 33°28'E, a ~300-430 km
  N-S plateau), is described in the surrounding Tuccia/Urbinia
  quadrangles as **"eucrite-rich howardite, though diogenite-rich
  howardite areas are also present"** — i.e. even this named, published
  unit is not compositionally homogeneous at the quadrangle scale.
- Attempted to fetch the actual global/quadrangle spectral-parameter
  maps for finer-grained lat/lon boundaries (De Sanctis/Ammannito/
  Frigeri's "Atlas of Vesta Spectral Parameters" and the per-quadrangle
  Icarus series): the ScienceDirect articles are paywalled (no full text
  reachable), and the one open-access source found (an arXiv PDF on
  Vesta's dielectric properties) could not be rendered in this
  environment (missing `poppler-utils` for PDF page extraction) —
  reported as a genuine access limitation, not glossed over.

**Honest conclusion, precise about what is and isn't established:** the
one well-established, high-confidence compositional boundary in the
literature — polar (Rheasilvia, ~72°S) diogenite vs. equatorial
eucrite/howardite — **does not explain our observed Band II
bimodality**, because all 15 of our real observations sit at -13° to
-29°, nowhere near that ~72°S boundary; our sample never crosses it.
Vestalia Terra (center ~34°E) sits closer to two of our cluster-1 points
(47-58°E) than to any cluster-0 point, but is itself described as
compositionally mixed at the quadrangle scale, and most of our 15 points
(96-333°E) are well outside it regardless. **No published map accessible
in this session has fine enough resolution/coverage at these specific
15 coordinates to say whether cluster 0's locations and cluster 1's
locations fall on documented different, or the same, geologic units.**
This is reported plainly as "no usable match found," not stretched into
either a confirmation or a refutation of the acquisition-session
confound hypothesis.

### Part B — LAMO acquisition: an independent structural test

Real orbital cadence, cross-checked (Planetary Society Dawn Journal
entries, citing mission parameters): **HAMO ~950 km altitude, ~12 hour
orbital period; LAMO ~180 km altitude, ~4 hour orbital period** — a real,
citable factor-of-3 difference, giving LAMO a structurally different
acquisition rhythm to test the confound against.

**Real LAMO directory verification, not assumed to mirror HAMO:** FC's
LAMO directory lists cycles 1-21 starting `2011347_CYCLE1`; VIR's LAMO
directory (both `DWNVVIR_V1B`/`DWNVVIR_I1B`) starts at
`20111231_CYCLE4` — **VIR cycles 1-3 are genuinely absent**, and the
nominal `20111231_CYCLE4` directory itself 404s. Querying the live
INDEX.TAB directly (not trusting directory names) found VIR's real
`CYCLE4`-labeled data is entirely dated **2012-01-08, an 8-9 day
schedule slip** from its nominal 2011-12-31 label; FC's own `CYCLE4`
real window (2012-01-01 to just before 2012-01-08 06:31) ends right as
VIR's begins, so the real temporal overlap is FC's *CYCLE5* against
VIR's *CYCLE4* — same nominal cycle numbers do not mean same real time
here, unlike HAMO. Added `lamo_cycle4` to `configs/config.yaml` using
the real, verified dates (2012-01-07 to 2012-01-09), not the nominal
directory-name dates — full reasoning recorded as a config comment.

**A second real bug found and fixed** (in `ml/data/pds_acquisition.py`,
not on this task's do-not-touch list): pulling FC data for this window,
168 of 336 INDEX.TAB rows 404'd. Diagnosis: this LAMO volume's INDEX.TAB
carries **two rows per real product** — one ending in `.LBL` under
`/DATA/FITS/` (the real label + `.FIT` pair, exactly as HAMO's rows
worked), and a second row whose `FILE_SPECIFICATION_NAME` points
*directly* at the `/DATA/IMG/` `.IMG` data file itself (not a label at
all). The old code assumed every row's path was a label and blindly
appended `.FIT` — silently 404s on the second row type, and would have
(if it happened to "succeed") saved a data file as if it were a label.
Verified server-side: every one of the 168 non-`.LBL` rows in this
window has an exact-match `.LBL` sibling row for the same real
`PRODUCT_ID` — so the fix filters to `.LBL`-referencing rows only (168
real unique products, not 336), logging a warning if any product were
ever found with *no* `.LBL` sibling (none were, here). Re-ran: 168/168
downloaded. Confirmed the earlier buggy runs had also re-introduced
manifest duplication (1850 entries / 1178 unique) — deduplicated again
by `product_id`, same method as Slice 9. `python -m pytest tests/ -q`:
33/33 still passing (this fix touches only URL/path construction, no
test covers it directly, but nothing regressed).

**Real alignment re-run** (unmodified `align_dataset()`, combined
HAMO+LAMO manifests):
```
Loaded geometry for 1178/1178 FC images (1168 usable footprint) and 140/140 VIR spectra (132 usable footprint)
Alignment: 28518 FC x 24 VIR candidates in 24h window; 28278 computable; 787/28278 survived >= 0.30
```
**787 total survivors (743 HAMO + 44 new from LAMO).**

**Chose LAMO-only (not combined) for the separability/confound test** —
combining would blur exactly the comparison this track needs (does
LAMO's *own* pattern replicate or break HAMO's). LAMO's 44 survivors
resolve to 20 unique VIR products; pairing by clock count (same function,
same script, unmodified) gives **8 real paired observations** (4 VIS-only
products excluded as genuinely unpaired — logged by the script's existing
warning, not hidden). All 8 usable.

| clock | Band I (μm) | Band II (μm) | lat | lon | time |
|---|---|---|---|---|---|
| 379294594 | 0.9209 | 1.9573 | -12.57 | 22.31 | 2012-01-08T11:35 |
| 379294841 | 0.9211 | 1.9573 | -18.49 | 17.67 | 2012-01-08T11:40 |
| 379295088 | 0.9210 | 1.9573 | -24.32 | 13.01 | 2012-01-08T11:44 |
| 379295335 | 0.9209 | 1.9574 | -30.08 | 8.35 | 2012-01-08T11:48 |
| 379310520 | 0.9214 | 1.9574 | -15.09 | 84.45 | 2012-01-08T16:01 |
| 379310767 | 0.9213 | 1.9574 | -21.11 | 79.79 | 2012-01-08T16:05 |
| 379311014 | 0.9213 | 1.9574 | -27.03 | 75.11 | 2012-01-08T16:09 |
| **379311261** | 0.9210 | **2.1643** | -32.85 | 70.42 | **2012-01-08T16:13** |

Silhouette (k=2/3/4): **0.8740 / 0.6175 / 0.5192**.

**A striking, load-bearing observation, reported precisely rather than
smoothed over**: LAMO's Band II values land at **almost exactly the same
two numbers HAMO produced** — ~1.957 μm and ~2.164 μm — not merely "also
bimodal," but numerically matching to ~0.001 μm across two entirely
independent mission phases. That level of exact numeric recurrence is
unusual for continuous geological variation and raises a **third
hypothesis this audit had not previously considered: a processing/
wavelength-grid quantization artifact** in the band-center-fitting
method itself (e.g. the parabola fit snapping to one of a small number
of positions on VIR's fixed `BAND_BIN_CENTER` sampling grid regardless of
subtle underlying spectral differences), which could produce clean-
looking bimodality that reflects instrument/algorithm behavior rather
than composition. This is flagged as a real, open alternative
explanation — not investigated further here, per this task's scope, but
recorded so it isn't silently missed by whoever labels next.

**Confound check, and the key structural result**: LAMO's 7 "≈1.957"
observations split into two real sessions the same day — 11:35-11:48 and
16:01-16:09, **~4.3 hours apart, matching LAMO's own ~4h orbital period**
— consistent with the same kind of session-driven rhythm HAMO showed.
**But the single "≈2.164" observation (379311261) is NOT in a separate
session**: it was acquired at 16:13, just **4 minutes after** the
previous "≈1.957" observation (379311014, 16:09) in the *same* orbital
pass, at a geographically adjacent location (lat -32.85/lon 70.42 vs.
-27.03/75.11 — a few degrees apart, consistent with the same ground
track). Illumination angles (incidence 45.25-46.48° vs. 46.23°;
emission 6.53-12.22° vs. 10.96°; phase 46.24-49.36° vs. 46.07°) do not
distinguish this point from its immediate neighbors either.

**This is a real, structural difference from HAMO's confound pattern,
reported honestly with its own sharp limitation**: in LAMO, a "different
Band II value" appeared immediately adjacent in time and space to
"same-session" neighbors, which HAMO's session-confound explanation
would not predict (if session/orbital-pass alone drove the split, this
point should have matched its session-mates, not jumped). That is weak
evidence *against* the acquisition-session confound generalizing to
LAMO, and weakly consistent with a real, spatially localized
compositional transition within a single orbital pass. It is **weak**
specifically because this is a single point (n=1) in the "≈2.164"
group — nowhere near enough to draw a population-level conclusion, and
exactly the same real number recurring from HAMO keeps the
quantization-artifact explanation just as live as the composition one.

### Bottom line across both tracks

**Neither track resolves the question — both narrow it, honestly.**
Track A: the one well-established published compositional boundary
(polar diogenite vs. equatorial eucrite/howardite) doesn't apply to
this sample's latitude range at all; no finer map was accessible to
check further. Track B: LAMO replicates HAMO's exact two Band II values
(raising a new, unresolved quantization-artifact hypothesis neither
track had considered before), while its one cross-session data point
weakly argues against (not for) the acquisition-session confound
specifically. **Three live hypotheses remain open — acquisition-session
confound, genuine localized composition, and band-center quantization
artifact — and this task does not adjudicate between them**, per its
explicit scope: no proceeding to `ml/data/spectral_labeling.py` or class
assignment regardless of these findings. That remains a decision point
for a follow-up conversation.

## Slice 12: testing the band-center quantization-artifact hypothesis (real data, unmodified code)

**Task**: Slice 11 raised, but did not test, a third hypothesis for the
recurring HAMO/LAMO Band II bimodality (~1.957 μm / ~2.164 μm): that it
is a fitting/quantization artifact of `compute_band_center()` rather than
genuine geology. This slice tests that one hypothesis, on real data,
without modifying `ml/data/spatial_alignment.py`, `ml/utils/splits.py`,
the specificity penalty, `ml/data/pds_acquisition.py`, or
`compute_band_center()` itself (diagnosis only — a fix, if warranted, is
an explicit follow-up). No labeling or class assignment attempted.

**Step 1 — real IR wavelength grid.** Pulled `BAND_BIN_CENTER` (via
`read_vir_qube()`, unmodified) for a real IR product and sliced it to
`BAND_II_WINDOW_UM` (1.65-2.50 μm): 90 real grid points, spacing
0.0090-0.0100 μm (mean 0.00945 μm) — i.e. genuinely ~0.0095 μm, as
suspected. Both cluster centers sit almost exactly on real grid points:
1.957 μm is an exact grid value; 2.165 μm is a grid value (the reported
2.164 μm cluster center is ~0.001 μm off it, within one parabola-fit
step). On its face, a ~0.0095 μm grid is coarse enough that this
hypothesis is plausible, not implausible — real Band II absorption
features on Vesta are broad (tens of nm), so this grid genuinely
undersamples the feature's true curvature.

**Step 2 — raw spectrum overlay.** Plotted real, unfitted
`mean_spectrum` values (not fitted centers) across `BAND_II_WINDOW_UM`
for three real comparison pairs: two within-cluster HAMO pairs
(370705798 vs 370749809, both fit ≈1.957; 370662589 vs 370750991, both
fit ≈2.165) and the LAMO cross-session pair (379311014 fit ≈1.957 vs
379311261 fit ≈2.164, 4 minutes apart). Saved to
`docs/handoff/artifacts/band_ii_raw_overlay.png`. Visually, all three
pairs show the same overall shape (a broad, shallow, gently undulating
decline with a shared sharp real feature near ~2.42-2.45 μm in every
curve) offset vertically from each other — not two visibly different
absorption-minimum shapes.

**Step 3 — numeric shape comparison (not just visual).** For each of the
6 real spectra behind these 3 pairs, computed the actual continuum-removed
curve (identical math to `compute_band_center()`, read-only) and listed
its lowest local minima by depth:

| clock | fit result | top-4 local minima (wavelength μm, continuum-removed depth), sorted |
|---|---|---|
| 370705798 | 1.9572 | (1.957, 0.6275), (2.165, 0.6317), (1.995, 0.6342), (2.014, 0.6385) |
| 370749809 | 1.9575 | (1.957, 0.5467), (1.995, 0.5562), (2.014, 0.5597), (2.165, 0.5619) |
| 370662589 | 2.1642 | (2.165, 0.6292), (1.957, 0.6359), (2.146, 0.6395), (1.995, 0.6416) |
| 370750991 | 2.1639 | (2.165, 0.6144), (1.957, 0.6162), (1.995, 0.6204), (2.014, 0.6236) |
| 379311014 | 1.9574 | (1.957, 0.6088), (2.165, 0.6178), (1.995, 0.6185), (2.014, 0.6206) |
| 379311261 | 2.1643 | (2.165, 0.6072), (1.957, 0.6089), (2.146, 0.6131), (1.995, 0.6163) |

**This is the central finding.** Every one of the 6 real spectra —
across both HAMO clusters and the LAMO cross-session pair — has the
same set of near-tied competing local minima (1.957, 1.995, 2.014,
2.165, sometimes 2.146 μm), differing only in the depth ranking of
which one happens to be lowest (typically by well under 2% relative
depth). The raw curves do not show genuinely different
absorption-minimum shapes; they show the same underlying multi-modal
curve shape, with whichever of ~2-4 near-degenerate candidate minima
narrowly wins the global-minimum search reported as "the" band center.
This directly answers step 3: it is a jumping fit output, not a
genuinely different physical minimum position.

**Step 4 — perturbation test (unmodified `compute_band_center()`, real
spectrum, synthetic perturbations only).** Base case: clock 370705798,
unperturbed fit = 1.95721 μm.

- Sub-grid wavelength shifts (interpolating the real spectrum onto a
  grid shifted by a fraction of the 0.0095 μm spacing, no noise): the
  output varied smoothly, from 1.95721 μm at shift=0 up to 1.96624 μm
  at a full grid-spacing shift — no discrete jump. This refutes the
  narrowest version of the hypothesis (a hard vertex round-to-grid
  snap dominating ordinary sub-pixel behavior): the parabola fit itself
  interpolates continuously when the same local minimum keeps winning.
- Additive Gaussian noise on the same real spectrum, 10 seeds per
  amplitude: at 0.1% of mean signal amplitude, output stayed smoothly
  clustered near 1.955-1.957 μm (no jump). At 0.5% amplitude, 2 of 10
  seeds jumped to ≈2.164-2.165 μm while the rest stayed near ≈1.957 μm —
  a discrete jump between exactly the two real cluster values, not a
  continuum in between. At 1.0-2.0% amplitude, the jump rate rose
  further (4-6 of 10 seeds landing in the ≈2.16 μm cluster), plus a
  handful of intermediate excursions (e.g. 2.0121, 2.0885, 2.1464) as
  noise grew large enough to occasionally favor other candidate minima
  from the step-3 table. 0.5-2% noise on a real spectrum's absolute
  values is well within realistic VIR measurement noise.

**This is the decisive result**: the same real, single spectrum, given
only realistic-amplitude random noise (no change in true underlying
composition), reports a fitted Band II center that discretely snaps
between the two exact values seen across independent HAMO and LAMO
observations, rather than varying continuously. Sub-grid shifts alone
produce smooth output; it is the global-argmin selection among several
near-tied local minima (step 3), not simple grid-rounding, that is
unstable — but the practical consequence is exactly the discrete,
repeated-value behavior the artifact hypothesis predicted.

**Step 5 — source inspection for snapping behavior.**
`ml/data/spectral_labeling.py`'s `compute_band_center()` picks the
global minimum of the continuum-removed curve via
`i = valid_idx[np.nanargmin(removed[valid_idx])]`, then fits a parabola
to only the 3 points immediately around that single global-argmin index.
When several candidate minima are nearly tied (as step 3 shows is the
norm here, not an exception), `nanargmin` deterministically picks
whichever one is marginally lowest for that sample's noise realization —
there is no mechanism to detect or report near-ties. Three additional
raw-grid-value fallback paths exist and were confirmed present, though
not the operative mechanism in this specific dataset's base (unperturbed)
fits, since `vertex_inside_window` was `True` for all 6 real spectra
checked in step 3:
- edge case: `if i == 0 or i == len(removed) - 1: return float(w[i])`
  — returns the raw, unmodified grid value with no interpolation.
- degenerate fit: `if denom == 0 or ...: return float(x1)` — same.
- non-parabolic fit: `if a == 0: return float(x1)` — same.
- out-of-window vertex: `if not (x0 <= vertex <= x2): return float(x1)`
  — silently discards the fit and returns the raw grid value whenever the
  parabola's own vertex estimate falls outside its local 3-point window.

These fallbacks are real and would compound the instability further
(exact grid-value repeats) whenever they trigger, but the step 4
perturbation test shows the dominant mechanism producing this dataset's
specific bimodality is upstream of them: the global-minimum search
itself flipping between near-degenerate candidates.

**Verdict: SUPPORTED.** The band-center quantization/fitting-artifact
hypothesis is supported by direct evidence, not merely plausible:
(1) the real IR grid (~0.0095 μm) is coarse relative to Vesta's broad
Band II feature; (2) all 6 real spectra checked share the same 3-4
near-tied competing local minima rather than one distinct minimum each;
(3) adding realistic (0.5-2%) noise to a single real spectrum, with no
compositional change, causes `compute_band_center()`'s real, unmodified
output to discretely jump between the exact two values recorded across
independent HAMO and LAMO observations. This does not by itself prove
there is no genuine compositional signal underneath — a real Band II
shift could exist and simply be too small relative to this fitting
method's noise sensitivity to see cleanly — but it does mean the
observed bimodality, as currently measured, cannot be trusted as
evidence of real composition without a more robust band-center method.
No fix is made here (out of scope for this task); the concrete follow-up
is to make `compute_band_center()` report a confidence/ambiguity flag
when multiple local minima are within some tolerance of the global one
(or to widen/smooth the fit window), then re-run the Slice 10/11 audits
before any labeling proceeds.

## Slice 13: fixing the band-center instability (compute_band_center_v2)

**Task**: Slice 12 found, with direct evidence, that `compute_band_center()`
discretely snaps between near-tied local minima under realistic noise.
This slice fixes it — diagnosis-to-fix, not labeling. Per explicit scope:
`ml/data/spatial_alignment.py`, `ml/utils/splits.py`, the specificity
penalty, and `ml/data/pds_acquisition.py` untouched (confirmed, `git diff
--stat` empty on all three); `compute_band_center()` itself is also
untouched — the fix lives entirely in a new function,
`compute_band_center_v2()`, added alongside it. No labeling or class
assignment attempted with the new method's output.

**Step 1 — fix approach chosen.** Option (b)(ii) from this task's menu:
ambiguity-aware fitting with a depth-weighted centroid across tied
candidates. Rejected option (a) (simply widening the single parabola
window) because Slice 12's competing minima are ~0.2 μm apart — wider
than any window that could still represent one physical absorption
feature; a single wider parabola would either miss a tied candidate or
badly misfit both. Rejected option (c) (a full Modified Gaussian Model)
because the diagnosed failure is a *multi-candidate selection*
instability (which of several genuine local dips wins an argmin), not a
poor local shape fit — directly modeling that ambiguity is the targeted
fix, without a full band-shape optimizer's added implementation risk.

**Two real design corrections found during this task's own validation**
(required by the task before finalizing anything — not assumed):

1. *Normalization.* An early draft measured "relative depth" against a
   candidate's raw continuum-removed value. Real Vesta Band II curves sit
   on a large, roughly-constant continuum-removed offset (~0.6-0.7, not
   near 0); normalizing against that offset directly made the tolerance
   far too permissive, pulling in 7+ shallow ripple-level points spanning
   nearly the whole window. Fixed by normalizing against the deepest
   candidate's own band depth (`1 - removed`) instead, which recovered the
   ~2-4 candidates Slice 12's manual inspection found.
2. *Hard cutoff → smooth weight.* A second draft used a hard tie/no-tie
   cutoff (a candidate is either "in" or "out" of a discrete group, then
   averaged). Validating that draft against Slice 12's own perturbation
   test (real spectrum, real noise) showed it reproduces a version of the
   exact jumping behavior it was meant to fix: small noise flips
   candidates across the hard boundary, and each flip discontinuously
   changes which points feed the average. Replaced with a smooth
   (soft-argmin / Boltzmann) depth-weighted centroid — every candidate
   always contributes some, possibly tiny, weight, so the output changes
   continuously as the input changes continuously. A further correction
   restricted this smooth weighting to genuine discrete local minima
   (not every sample in the window): weighting every sample flagged any
   sufficiently broad single real feature as "ambiguous" too, since
   neighboring samples near one smooth trough's bottom are naturally
   close in depth — which fails step 4's single-minimum correctness
   requirement outright. Final design: find discrete local minima, fit
   each one's own sub-pixel vertex (identical parabola math to
   `compute_band_center()`), then combine with the smooth weight.

`BandCenterResult` adds `ambiguous` (bool), `confidence` (0-1, from the
weight distribution's participation ratio — 1.0 when one candidate
carries all the weight), and `n_candidates` (effective number of
competing local minima), alongside `center_um`.

**Step 2/4 — validation.**

*Perturbation test (clock 370705798, unperturbed old fit = 1.95721 μm)*:

| noise amplitude | old method spread (10 seeds) | v2 spread (10 seeds) |
|---|---|---|
| 0.1% | 0.00016 μm | 0.00896 μm |
| 0.5% | 0.20842 μm (already at the jump plateau) | 0.04283 μm |
| 1.0% | 0.20975 μm | 0.07923 μm |
| 2.0% | 0.21170 μm | 0.11449 μm |
| 5.0% | 0.21488 μm | 0.15203 μm |

The old method's spread jumps to its ~0.21 μm plateau almost immediately
(between 0.1% and 0.5% noise) and stays flat — the discrete bimodal
snap. v2's spread grows smoothly and monotonically with noise amplitude
instead, with no discrete jump at any tested level. Sub-grid wavelength
shifts (no noise) also produced smooth v2 output (2.044 → 2.012 μm across
a full grid step). This is the qualitative signature step 3a required:
"varies smoothly," not "jumps between two values."

*Correctness check (single clean synthetic minimum, no near-ties)*: v2
returned `ambiguous=False`, `confidence=1.0`, `n_candidates=1`, and
matched the old method's output to within 1e-6 μm — confirming the fix
does not change behavior on genuinely unambiguous features.

*Full real dataset (23 real paired observations: 15 HAMO + 8 LAMO, same
manifests as Slices 10/11, no new downloads)*: **all 23 of 23 flag
`band_ii_ambiguous=True`** (and all 23 also flag `band_i_ambiguous=True`).
This is itself an important, honest finding: the instability Slice 12
diagnosed is not confined to a couple of edge-case spectra — under a
properly-normalized, evidence-based ambiguity test, every single real
Band II (and Band I) fit in this dataset shows a genuinely competing
near-tied local minimum. New Band II center values ranged 2.0016-2.0782 μm
across the 23 observations (full per-clock table in
`scripts/audit_band_separability_v2.py`'s output) — notably, this range
sits *between* the two original clusters (~1.957 and ~2.164 μm), not on
either one, consistent with the centroid honestly averaging competing
candidates rather than picking a side.

**Step 3 — re-run silhouette scores, same real data, v2 method (both
bands switched to v2 for internal consistency — see
`scripts/audit_band_separability_v2.py`'s docstring for why)**:

| dataset | old method (buggy) | v2 method |
|---|---|---|
| HAMO-only, n=15 (Slice 10 baseline) | 0.9982 / 0.9058 / 0.7234 | **0.590 / 0.621 / 0.588** |
| LAMO-only, n=8 (Slice 11 baseline) | 0.8740 / 0.6175 / 0.5192 | **0.607 / 0.669 / 0.468** |
| Combined, n=23 (no old-method baseline exists for this exact split) | — | 0.538 / 0.581 / 0.551 |

**A substantial drop, reported exactly as measured — not a total
collapse.** The old method's near-perfect scores (0.90-1.00 at the best
k for each dataset) do not survive the fix; v2 lands in the 0.47-0.67
range across every k and every dataset — conventionally "moderate,
real-but-weak" clustering structure, not "no structure at all" (which
would show near-zero or negative scores) and not "clean separation
either" (which the old numbers falsely suggested).

**Verdict: Slice 12's diagnosis is substantially confirmed, not fully
resolved into either extreme.** The dramatic, near-perfect bimodal
separation reported in Slices 10-11 does not survive a fitting method
that is demonstrably robust to the exact noise level that broke the old
one — most of what looked like clean structure was very likely the
diagnosed artifact. But silhouette scores in the 0.47-0.67 range are not
nothing: some real clustering signal in (Band I, Band II) space persists
under the more honest method, and 23/23 observations being flagged
ambiguous means the *entire* dataset's Band II fits carry real
uncertainty that a compositional-labeling pass would need to account for
directly (e.g. propagate `confidence` as a per-sample weight, or exclude
low-confidence samples), not average away. This does not, by itself,
tell us whether the surviving ~0.5-0.6 silhouette reflects genuine Vesta
geology, a residual (weaker) version of the session confound Slice 11
found, or some other structure — that question is explicitly out of
scope here and belongs to whatever task takes on labeling next.

**What was not done, stated plainly**: no attempt was made to tune
`BAND_CENTER_TIE_TOLERANCE` (0.03) to land on any particular silhouette
result — it was fixed by the physical reasoning in Step 1, before this
step's numbers were known, per this task's explicit constraint. A full
Modified Gaussian Model fit (option c) was not implemented; if the
surviving ~0.5-0.6 structure is judged worth pursuing further, an MGM
fit (or an independent noise-floor characterization from VIR's actual
documented instrument specs, rather than this task's illustrative
Gaussian/uniform-shift perturbation models) would be the natural next
methodological step before labeling.

## Slice 14: does the acquisition-session confound survive the v2 fix?

**Task**: Slice 13 left open whether the ~0.5-0.6 silhouette structure
surviving `compute_band_center_v2()` is genuine geology or a weaker
residual of Slice 11's acquisition-session confound. This slice answers
that specific question with a real cross-tabulation, on the same 23 real
combined HAMO+LAMO observations, same manifests, no new downloads. Per
scope: `ml/data/spatial_alignment.py`, `ml/utils/splits.py`, the
specificity penalty, `ml/data/pds_acquisition.py`, and
`compute_band_center_v2()` itself are all untouched (confirmed, `git diff
--stat` empty on all four). No labeling attempted. New script:
`scripts/recheck_confound_v2.py` (reuses `pair_observations_by_clock()`
and `confound_summary()` from `audit_band_separability.py` and
`extract_band_points_v2()` from `audit_band_separability_v2.py`,
unmodified imports).

**Step 1 — v2 k=2 cluster assignment** (same KMeans call the silhouette
score already used, `random_state=42, n_init=10`, on the real v2 (Band I,
Band II) points): **cluster sizes 11 and 12** — a far more balanced split
than the old method's tight, near-discrete 6/9 (HAMO) and 7/1 (LAMO)
groups, consistent with v2's centroids landing on a continuous range
(2.0016-2.0782 μm) rather than two sharp values.

**Step 2/3 — real session grouping vs. v2 cluster.** Sessions defined by
a real, data-driven gap rule: a new session starts whenever the gap since
the previous real `START_TIME` exceeds 30 minutes (HAMO's real within-
session gaps are ~9-10 min, between-session gaps ~11h44m-12h17m; LAMO's
are ~4 min and ~4h13m — any threshold between ~20 min and several hours
gives the identical 6 real sessions, so this is not a tuned choice). Each
observation is checked against its own session's majority cluster:

```
session 0 (HAMO, 2011-09-30 ~01:12-01:41, n=4): clusters [0,0,0,1]
session 1 (HAMO, 2011-09-30 ~13:29-13:58, n=4): clusters [0,0,0,0]
session 2 (HAMO, 2011-10-01 ~01:49-02:18, n=4): clusters [0,1,1,1]
session 3 (HAMO, 2011-10-01 ~14:02-14:22, n=3): clusters [1,0,0]
session 4 (LAMO, 2012-01-08 ~11:35-11:48, n=4): clusters [1,1,1,1]
session 5 (LAMO, 2012-01-08 ~16:01-16:13, n=4): clusters [1,1,1,0]
```

**Real cross-tabulation: 19 of 23 observations' v2 cluster assignment
matches their own session's majority cluster** (HAMO: 12 of 15 = 80%;
LAMO: 7 of 8 = 87.5%). This is weaker than Slice 11's old-method finding
for HAMO (14 of 15 = 93%), but still clearly well above the 50% a random
binary split would give — **the session confound weakens under the fix,
it does not disappear.** Notably, both of Slice 11's originally-flagged
"exception" points — `370749809` (HAMO) and `379311261` (LAMO), the two
observations whose old-method cluster broke the clean session pattern —
**are still mismatches under v2**, the same direction as before. Two
*new* mismatches also appear (`370618943` in session 0, `370705798` in
session 2) that were not exceptions under the old method — the specific
error pattern shifted, not just shrank uniformly.

**Step 4 — geography and illumination angle, re-checked against the NEW
clusters (not assumed from Slice 10's old-method conclusion):**

| cluster (n) | incidence (min/med/max) | emission (min/med/max) | phase (min/med/max) | latitude (min/med/max) | longitude (min/med/max) |
|---|---|---|---|---|---|
| 0 (11) | 28.08/30.48/46.23 | 6.24/8.87/10.96 | 30.19/31.99/46.07 | -32.85/-18.40/-13.63 | 58.18/107.20/333.00 |
| 1 (12) | 27.87/45.31/46.47 | 6.51/9.88/12.27 | 30.13/46.25/49.36 | -30.08/-22.71/-12.57 | 8.35/77.45/210.77 |

Latitude and longitude ranges overlap substantially in both clusters
(same conclusion as Slice 10: not a fixed two-region split). **But
incidence and phase angle medians differ sharply between clusters (~30°
vs ~45°)** — a new result Slice 10/11 could not have surfaced, because
they analyzed HAMO and LAMO separately and never combined the two phases
into one clustering. Checking the reason directly: **this tracks mission
phase, not composition.** Cluster 0 is 10 of 11 members HAMO (91%);
cluster 1 draws 7 of 12 members from LAMO (58%, versus LAMO's 35% overall
share of the 23-point sample) — HAMO and LAMO fly at very different
altitudes or (~950 km vs ~180 km) with correspondingly different real
viewing/illumination geometry for orbital-mechanical reasons that have
nothing to do with surface composition. A Fisher exact test on the 2×2
(mission × cluster) table gives **odds ratio 14.0, p = 0.027** — a real,
statistically notable association at this sample size, not
over-interpretation of a small numeric gap.

**This is the single most important finding of this recheck: a new
confound — mission phase — emerges under v2 that the earlier,
phase-separated analyses structurally could not detect**, because Slice
10 clustered HAMO alone and Slice 11 clustered LAMO alone. Combining both
phases into one clustering (needed to get from n=15/n=8 up to the n=23
this task and Slice 13 use) risks manufacturing apparent structure from
procedural/instrumental differences between mission phases themselves,
not from geology.

**Step 5 — cluster vs. fit confidence** (all 23 observations are
flagged `ambiguous=True` for both bands, per Slice 13 — this checks
whether confidence still varies systematically by cluster within that):

| cluster (n) | Band II confidence (min/median/max/mean) |
|---|---|
| 0 (11) | 0.121/0.136/0.145/0.134 |
| 1 (12) | 0.114/0.159/0.223/0.164 |

A Mann-Whitney U test on Band II confidence by cluster gives **p =
0.0042** — a real, statistically significant association: cluster 0 does
fit measurably less confidently than cluster 1. Checking whether this is
just the same mission-phase story again (LAMO's median confidence, 0.151,
is somewhat higher than HAMO's, 0.138, overall): **partially, not
fully.** Restricting to HAMO observations only (holding mission phase
fixed), cluster 1 still shows a higher median confidence than cluster 0
(0.166 vs 0.137), but the difference is no longer statistically
significant at this reduced sample size (Mann-Whitney p = 0.16, n=15).
So: part of the overall confidence/cluster association is attributable
to the mission-phase confound above; a smaller, same-direction, not
independently significant residual trend persists within HAMO alone.

**Verdict, stated plainly and not resolved toward either extreme**:
**the picture is messier than either Slice 11's or Slice 13's framing
anticipated — if anything, more entangled with non-compositional factors
than less.** The acquisition-session confound weakens under the v2 fix
(93%→80-88% session-majority match) but does not disappear. A genuinely
new confound — mission phase, and the illumination-geometry difference
it carries — emerges with real statistical support (p=0.027) that the
phase-separated Slice 10/11 analyses could not have caught. Fit
confidence also correlates with cluster assignment (p=0.0042 overall),
though roughly half of that appears to be the mission-phase confound
showing up again rather than an independent artifact. **None of the
three checked factors (session, mission phase, confidence) is cleanly
ruled out, and none on its own fully explains the surviving ~0.5-0.6
silhouette structure either.** This task does not adjudicate between
"weakened session confound," "mission-phase/illumination confound," and
"some genuine but small compositional signal riding on top of both" —
it reports that all three remain live, with real numbers attached to
each, exactly as instructed. No labeling proceeds from this finding.

**Concrete next steps this surfaces, not undertaken here**: (1) re-run
the v2 clustering and silhouette analysis separately within HAMO and
within LAMO (as Slice 10/11 originally did with the old method) to
isolate the surviving structure from the newly-found mission-phase
confound before combining phases again; (2) if a next task pursues
labeling, it should not treat `confidence` as a nuisance parameter to
average away — Step 5 shows it is not independent of cluster assignment.
