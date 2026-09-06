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
