# Handoff Status Log

Append-only. Never edit or delete a previous session's entry, even to
"clean it up" — if something in an old entry turns out to be wrong, add a
new entry noting the correction with the reason.

Every claim under "Real results" is something actually run and observed
in that session — not inferred, not assumed to still hold from an earlier
session. See `docs/month1_log.md` for the full narrative/evidence behind
each session; this file is the terse, chronological index.

---

## Session 1 — 2026-09-10 — commit 495d127

**Task attempted:** Retroactive summary of all work already completed on
`month1-data-pipeline` prior to the handoff-convention setup — three
prior task instructions, executed across commits `328cd6f`, `7854c14`,
`495d127`: (1) fix the data-acquisition source so FC/VIR footprint
geometry and time-overlap actually exist, (2) fix the FC/VIR longitude-
sign convention bug that fix #1 exposed, (3) calibrate the size-ratio
specificity penalty against real data now that fix #2 exposed genuine
(if faint) overlap. This entry is retroactive — reconstructed from the
real, already-committed `docs/month1_log.md` (Slices 6-8), not re-derived
from memory.

**What actually changed** (three separate commits, each independently
verified not to touch the other two's protected files):

- `328cd6f` — `ml/data/pds_acquisition.py`, `configs/config.yaml`:
  added `filter_rows_by_phase()` + a `phase=` parameter on
  `fetch_framing_camera_images()`/`fetch_vir_spectra()`, filtering
  INDEX.TAB rows by real parsed `START_TIME` against a verified
  `data.mission_phases` date-window table (including `hamo_cycle1`,
  2011-09-29 to 2011-10-05 — confirmed against real FC/VIR directory
  listings before coding). `ml/data/spatial_alignment.py`,
  `ml/utils/splits.py`, `ml/data/spectral_labeling.py` untouched
  (confirmed by empty `git diff` at the time).
- `7854c14` — `ml/data/spatial_alignment.py`,
  `tests/test_spatial_alignment.py`: removed the old uniform
  `_lon_to_x()`/`_x_to_lon()` transform (built from VIR-only evidence);
  added `_standardize_footprint_lon(west, east, instrument_id)`, called
  once in `load_geometry()` — FC values passed through unchanged
  (confirmed standard/east-increasing by FC's own SIS doc and 20/20 real
  samples), VIR values swapped (confirmed west-positive by 20/20 real
  samples; VIR's own SIS doc is ambiguous/inconsistent on this point,
  noted honestly rather than forced to look resolved).
  `ml/data/pds_acquisition.py`, `configs/config.yaml` phase filtering,
  `ml/utils/splits.py` untouched.
- `495d127` — `ml/data/spatial_alignment.py`,
  `tests/test_spatial_alignment.py`: replaced the inline
  `1.0 / size_ratio` specificity penalty with
  `compute_size_ratio_penalty()` — 1.0 (no discount) for size_ratio ≤ 5.0,
  decaying as `5.0/size_ratio` beyond that. Calibrated against the real
  distribution across all 1600 real HAMO-cycle-1 candidate pairs (every
  one falls between 1.88x-4.04x). Same three protected files/areas
  untouched.

**Real results** (all independently re-verified against the real data
already on disk, per `docs/month1_log.md`'s Slices 6/7/8 — not rounded or
smoothed):

| | Slice 6 (acquisition fix) | Slice 7 (longitude fix) | Slice 8 (penalty calibration) |
|---|---|---|---|
| FC frames with usable footprint | 160/200 (was 0/40 pre-fix) | 160/200 | 160/200 |
| Candidate pairs inside 24h window | 1600 (was 0 pre-fix) | 1600 | 1600 |
| Max confidence across all 1600 | 0.0172 | 0.1574 (9.2x higher) | n/a (post-threshold) |
| Nonzero-confidence pairs | 122 | 6 | 6 |
| Survivors at 0.30 threshold | **0** | **0** | **1** |

Final surviving pair (Slice 8): FC `0007112` / VIR
`VIR_VIS_1B_1_370617178`, confidence **0.30461421...**, real overlap
region lat[-17.77,-7.69] lon[82.84,88.34], real time delta 358.6 seconds
(~6 min), size_ratio 1.93x, overlap_coefficient 0.305. Test suite:
33/33 passing (`tests/test_spatial_alignment.py` + prior
`tests/test_metadata_schema.py`).

**Verified how:**
- Re-ran `python -m ml.data.spatial_alignment -v` at the end of each of
  the three sessions against the real, already-downloaded HAMO-cycle-1
  data (200 FC products, 100 VIR products, no re-download) and read the
  actual log output (pair counts, footprint counts) directly.
- Ran `python -m pytest tests/ -q` after each change — 30/30 (Slice 6/7),
  33/33 (Slice 8).
- For the longitude fix: confirmed the regression tests fail against the
  pre-fix code via `git stash` (temporarily reverting
  `spatial_alignment.py`, re-running pytest, observing the resulting
  `ImportError`), then restored the fix and re-ran to confirm pass.
- For the penalty calibration: hand-verified the single surviving CSV row
  in `datasets/metadata/sample_metadata.csv` (full provenance fields
  populated, label still `unlabeled`/`pending` as expected) and opened
  the written crop `datasets/processed/0007112__VIR_VIS_1B_1_370617178.png`
  with PIL to confirm it's a real, non-empty 300×551 image.
- Cross-checked FC's and VIR's real SIS documents
  (`DWNVFC2_1B/DOCUMENT/SIS/DAWN_FC_SIS_20131216.HTM`,
  `DWNVVIR_V1B/DOCUMENT/SIS/DAWN_VIR_SIS_V1_8.HTM`) directly, quoting
  their exact wording rather than inferring convention from data alone.

**Open issues / blockers:**
- **N=1 real, spatially-verified pair.** This is nowhere near enough
  sample volume to proceed to VIR-based labeling (`ml/data/spectral_labeling.py`)
  or a 3-way model comparison — a single sample can't populate even one
  class. This is now an **acquisition-volume** problem, not a
  pipeline-correctness one: all three originally-flagged issues
  (acquisition source, longitude convention, size-ratio penalty) are
  fixed and verified against real data, and the pipeline demonstrably
  finds and correctly scores a genuine correspondence when one exists.
- This batch only pulled 200 of 5080 available FC frames and 100 of
  ~160 available VIR spectra within the single verified `hamo_cycle1`
  window (2011-09-29 to 2011-10-05) — a small fraction of even one
  week, let alone the ~74-day HAMO phase or the LAMO phase.
- The clear next step (not yet started): a larger acquisition pull
  within the already-verified HAMO/LAMO windows, using the
  now-validated alignment pipeline unchanged, to get real sample volume
  before attempting labeling/splits/model comparison for real.

**Branch/commit:** `month1-data-pipeline`, commit `495d127`, pushed: yes
(all three constituent commits — `328cd6f`, `7854c14`, `495d127` — were
individually pushed to origin at the time).

---

## Session 2 — 2026-09-10 — commit (this entry's own commit — see `git log`, "Month 1 Slice 9")

**Task attempted:** Instruction relayed via `docs/handoff/NEXT.md`'s
intended content (pasted directly by the human, since the file itself
was never actually written to on disk — see Open issues): scale up
acquisition within the already-verified `hamo_cycle1` window (do not
touch the longitude standardization or specificity penalty) and re-run
`align_dataset()` to determine whether Session 1's N=1 result was a
sampling artifact or genuine scarcity.

**What actually changed:**
- No source files changed this session — `ml/data/pds_acquisition.py`,
  `ml/data/spatial_alignment.py`, `ml/utils/splits.py` all untouched.
- Real data changed: `datasets/raw/dawn_vir_vesta/` gained the full
  `hamo_cycle1` VIR set (80 real primary cubes, up from ~80 already
  mostly present); `datasets/raw/dawn_fc_vesta/` gained ~800 new real FC
  frames (1000 total in this window, up from 200).
- `datasets/raw/dawn_fc_vesta/manifest.jsonl` and
  `.../dawn_vir_vesta/manifest.jsonl` were **deduplicated in place** (a
  data fix, not a code fix — see Open issues) after discovering they'd
  accumulated massive duplicate entries across this session's and prior
  sessions' acquisition calls.
- `datasets/metadata/sample_metadata.csv` and `datasets/processed/*.png`
  regenerated by `align_dataset()` (743 rows / 743 crops) — these are
  gitignored data artifacts, not part of the commit.
- `docs/month1_log.md`: new "Slice 9" section with the full narrative.

**Real results:**

| | Session 1 (Slice 8) | Session 2 (Slice 9) |
|---|---|---|
| FC frames on disk (this window) | 200 | 1000 |
| VIR spectra on disk (this window) | ~80-100 (mixed) | 120 (deduplicated, all real) |
| Candidate pairs in 24h window | 1600 | 25,158 |
| Pairs with computable overlap | 1600 | 24,918 |
| **Survivors at 0.30 threshold** | **1** | **743** |
| Confidence range of survivors | 0.3046 (single value) | min 0.300, median 0.771, max 0.9996 |
| time_delta_seconds range | 358.6 (single value) | min 2.9, median 286.4, max 767.5 |
| spatial_iou range | 0.116 (single value) | min 0.114, median 0.362, max 0.547 |

**A real bug found mid-session, not swept past:** before trusting any of
the above, an intermediate alignment run against the *undeduplicated*
manifests (2200 FC entries for only 1010 unique products; 180 VIR
entries for 120 unique products — `_write_manifest()` appends without
deduplicating, across every acquisition call ever made in this repo)
produced a **2179-survivor** result. That number is **not** reported
above as real — it would have double/triple/quadruple-counted the same
real candidate pairs. Deduplicated the two manifest files by
`product_id` (data-only fix) before re-running for the real 743 figure.

**Verified how:**
- Re-ran `python -m ml.data.pds_acquisition --instrument fc --phase hamo_cycle1 --limit 1000 -v` (twice — once got 997/1000 with 3 transient network failures, confirmed by the actual error messages logged; re-ran the same command, which used the existing skip-if-exists logic to cheaply retry only the 3 missing ones, got 1000/1000).
- Ran `python -m ml.data.pds_acquisition --instrument vir --phase hamo_cycle1 -v` (no limit) and read the real log output (80/80 VIR downloaded).
- Directly inspected both manifest.jsonl files with a Python one-liner
  (`Counter` over `product_id`) to find and quantify the duplication
  before trusting any downstream number — this is what caught the
  inflated 2179 figure.
- Re-ran `python -m ml.data.spatial_alignment -v` against the
  deduplicated manifests and read the real log output for the 743
  figure.
- Loaded `datasets/metadata/sample_metadata.csv` with pandas and checked:
  row count vs. unique `region_id` count (743 == 743, no duplicate
  rows), confidence/time-delta/IoU min/median/max, that `label`/
  `label_source`/`split` were untouched (`unlabeled`/`pending`/
  `unassigned` on all 743 rows), and that the first row exactly matches
  Session 1's single survivor (same product IDs, same confidence value
  to 13 decimal places) as a continuity check.
- Counted files in `datasets/processed/` (743, matching the CSV) and
  confirmed `python -m pytest tests/ -q` still reports 33/33 passing
  (no test file changed, but re-run to confirm nothing regressed).

**Open issues / blockers:**
- **`docs/handoff/NEXT.md` was never actually written to on disk** — the
  human relayed its intended content directly as a chat message instead.
  This session's `NEXT.md` file itself is still just the original
  placeholder comment. Whoever writes the *next* real task into it should
  know this session's "Session 2" task came from a message, not the file,
  so there's no file history to cross-reference for it.
- **`pds_acquisition.py`'s `_write_manifest()` append-without-dedup
  behavior is a real, unfixed latent bug** (fixed here only as a
  post-hoc data cleanup, not in code, since this session's task
  explicitly scoped out touching acquisition code). It will recur on
  every future incremental/resumed pull. Needs a real code fix (dedup-
  on-write, keyed by `product_id`, or rebuild-the-manifest-from-disk each
  run) in a dedicated pass.
- **Only 1000 of 5080 available FC frames in `hamo_cycle1` were pulled**
  (a disclosed, bounded scope reduction — the full pull was estimated at
  6+ hours at the observed ~4.6s/product real download rate, impractical
  for one interactive session). The remaining ~4080 FC frames in this
  same window were not attempted.
- **Class balance for labeling is still unknown** — 743 surviving image
  crops resolve to only 30 unique VIR spectra; real compositional label
  diversity is bounded by those 30 spectra's real Band I/II
  measurements, not by 743. This is a question for the labeling pass,
  not resolved here.
- Labeling/splits (`ml/data/spectral_labeling.py`, `ml/utils/splits.py`)
  deliberately not started, per this task's explicit scope boundary —
  left for a dedicated next task.

**Branch/commit:** `month1-data-pipeline`, this entry's own commit
(see `git log` on this branch — "Month 1 Slice 9: scale up acquisition
— 743 real survivors (up from 1)"), pushed: yes.

---

## Session 3 — 2026-09-10 — this entry's own commit (see `git log`, "Month 1 Slice 10")

**Task attempted:** VIR spectral diversity audit on the 743 Slice-9
survivors' underlying VIR spectra (Part 1), plus a required addendum
raising the evidentiary bar: a quantitative separability check
(silhouette scores, not just a scatter plot), a confound check (ruling
out geography/illumination/time as spurious drivers of any apparent
grouping before trusting it), and a documented (not yet implemented)
split-leakage constraint for `ml/utils/splits.py`. Note: no prior
"Slice 10" or "Session 3" existed anywhere in this repo before this
session — verified via `git log` and `grep` over `month1_log.md`/
`STATUS.md` before starting; the implied prerequisite ("the main audit
task," a scatter plot of the 30 spectra) was built for real in this
session rather than assumed to already exist.

**What actually changed:**
- New `scripts/audit_band_separability.py` — real, re-runnable, read-only
  with respect to every `ml/` module (reuses
  `ml.data.spectral_labeling`'s already-tested QUBE reader/band-depth/
  band-center functions and `ml.data.spatial_alignment`'s generic PDS3
  scalar-field parser rather than reimplementing either).
- `ml/utils/splits.py`: **one docstring paragraph added, no logic
  changed** — a TODO cross-referencing this session's split-leakage
  finding for whoever next touches `assign_region_based_splits()`.
  Confirmed via `python -m pytest tests/ -q` (33/33, unchanged) that
  this was a documentation-only change.
- `docs/month1_log.md`: new "Slice 10" section (structural correction on
  30 products vs. 15 real observations, the real Band I/II table, the
  silhouette results for k=2/3/4, the full confound check, and the
  split-leakage note verbatim).

**Real results:**
- **30 unique VIR products (from Slice 9's 743 survivors) pair cleanly
  into exactly 15 real observations** (VIS+IR matched by shared
  `SPACECRAFT_CLOCK_START_COUNT`), zero unpaired singletons. The
  diversity question is about 15 observations, not "30 spectra" — this
  addendum's own framing used the higher, imprecise number, corrected
  here.
- **15/15 observations passed both bands' depth-floor gate** — 100%
  usable, 0 excluded from the 2D (Band I, Band II) analysis.
- **Band I center is nearly flat across all 15**: 0.9212–0.9221 μm (a
  ~0.001 μm spread). **Band II center is clearly bimodal**: 9 near
  1.957 μm, 6 near 2.164 μm (~0.2 μm separation, ~200x Band I's spread).
- **Silhouette scores** (KMeans, `random_state=42`): k=2 **0.9982**,
  k=3 0.9058, k=4 0.7234 — all three reported, not cherry-picked.
- **Confound check**: illumination angles (incidence/emission/phase)
  overlap substantially between the two k=2 clusters — not a confound.
  Ground location (latitude/longitude) also overlaps substantially
  between clusters (longitude spans 96–333° in one cluster and 47–222°
  in the other, clearly overlapping; latitude medians nearly identical,
  -20.5° vs -19.8°) — **not two fixed geographic regions**, ruling that
  out as the explanation. **Acquisition time/session is strongly
  correlated with cluster membership in 14 of 15 observations** (an
  early-morning acquisition block vs. an early-afternoon block,
  recurring across two different calendar days), with exactly one real
  exception — a strong but not perfect confound, reported as the
  genuine open question this audit surfaces, not resolved either way.
- **Bottom line, stated plainly**: a near-perfect silhouette score does
  NOT mean this sample supports a confident class assignment — this
  15-observation sample cannot separate genuine compositional signal
  from a real, identified acquisition-session confound. Quantitative
  clustering does not support proceeding to labeling on this specific
  sample.
- **Split-leakage note (verbatim in month1_log.md and cross-referenced
  in splits.py)**: 743 crops / 30 spectra, median 24.5 crops per
  spectrum (real number, min 8, max 32) — future splits must group by
  `spectrum_product_id`, not region/crop, or label information leaks
  across train/test. Not implemented this session, per explicit
  instruction.

**Verified how:**
- `git log --oneline` and `grep -n "Slice 10\|Session 3"` over both log
  files, run before starting, to confirm no prior work existed to build
  on or risk duplicating.
- Directly inspected `datasets/metadata/sample_metadata.csv` with pandas
  to confirm the 30-unique-product / 15-unique-observation pairing
  (grouped by regex-extracted clock-count suffix, checked 0 unpaired)
  before writing any extraction code around that assumption.
- Directly checked `ProductGeometry`'s actual field list in
  `ml/data/spatial_alignment.py` (source read, not assumed) and found it
  does NOT include `INCIDENCE_ANGLE`/`EMISSION_ANGLE`/`PHASE_ANGLE` —
  contrary to what this session's task description claimed; parsed
  those three fields directly in the new script instead, reusing only
  the existing generic scalar-parsing helpers, and confirmed by grep
  that a real downloaded label actually has them populated
  (non-`"N/A"`) before relying on them.
  Also pulled `CENTER_LATITUDE`/`CENTER_LONGITUDE` (not requested by
  the task, but essentially free with the same parser and directly
  decisive for the geography-confound question) and confirmed those
  fields are present in a real label before using them.
- Ran `python scripts/audit_band_separability.py` and read its real,
  printed output directly (no post-processing or rounding of the
  printed table/scores before transcribing into `month1_log.md`).
  Re-ran it after adding the location-confound check to confirm the
  silhouette numbers were unchanged (they were — that addition only
  changed what gets printed for the confound section, not the
  clustering inputs).
- `python -m pytest tests/ -q`: 33/33 passing after the `splits.py`
  docstring addition (confirms it's documentation-only, no behavior
  change).

**Open issues / blockers:**
- **Go/no-go for labeling: still not ready** — same conclusion in kind
  as before Slice 9 fixed the volume problem, but for a different,
  sharper reason now: volume exists (Slice 9), but this specific
  15-observation sample can't separate composition from an
  acquisition-session confound. Two concrete next steps recorded in
  `month1_log.md`: pull VIR pairs from additional HAMO cycles (2-6) or
  another phase so session and composition stop being perfectly
  correlated in the combined sample; and note that Band I's near-total
  flatness may itself reflect a coverage limitation (this single
  1-week window may not span enough real Ca-pyroxene variation for
  Band I to move at all), which is a volume problem the silhouette
  check surfaced rather than masked.
- **Split-leakage fix not implemented** (deliberately, per this
  session's explicit instruction) — `assign_region_based_splits()`
  still needs to be extended to group by `spectrum_product_id` before
  any real Month 2 training split is cut. Flagged in both
  `month1_log.md` and a `splits.py` code comment for whoever picks this
  up.
- This session ran on top of unrelated same-session work (installing
  and running the third-party `graphify` tool via its own CLI, unrelated
  to AstromineAI) — mentioned here only because it means this session's
  chat history is not a clean single-topic record; nothing from that
  work touched this repo's tracked files.

**Branch/commit:** `month1-data-pipeline`, this entry's own commit (see
`git log` on this branch — "Month 1 Slice 10"), pushed: yes.

---

## Session 4 — 2026-09-10 — this entry's own commit (see `git log`, "Month 1 Slice 11")

**Task attempted:** Investigate Slice 10's acquisition-session confound
via two independent tracks: (A) literature cross-check of the 15 real
HAMO observations' lat/lon against published Dawn VIR Vesta compositional
maps; (B) pull real LAMO-phase data (a structurally different, ~4h vs.
HAMO's ~12h, orbital cadence) and re-run the unmodified alignment +
separability pipeline to see if the same bimodality recurs and whether
it tracks LAMO's own time pattern. Explicitly scoped to NOT proceed to
labeling/class assignment regardless of findings.

**What actually changed:**
- `configs/config.yaml`: added `lamo_cycle4` to `data.mission_phases`,
  with the *real, verified* dates (2012-01-07 to 2012-01-09) — not the
  nominal directory-name dates, which were wrong by 8-9 days (see below).
- `ml/data/pds_acquisition.py`: **one real bug fixed** — FC row
  filtering now keeps only INDEX.TAB rows whose
  `FILE_SPECIFICATION_NAME` ends in `.LBL` (this LAMO volume carries a
  second, redundant row type per product pointing directly at the
  `.IMG` data file, which the old code wrongly treated as a label).
  Not on this task's do-not-touch list (`ml/data/spatial_alignment.py`,
  `ml/utils/splits.py`, specificity penalty — none touched).
- Real data: pulled 168 real FC LAMO products + 20 real VIR LAMO
  products (8 real paired VIS+IR observations after clock-count
  pairing). Manifests deduplicated again afterward (the buggy runs
  before the fix re-introduced duplication, same failure mode as
  Slice 9 — caught and fixed the same way).
- `docs/month1_log.md`: new "Slice 11" section, Parts A and B, written
  in that order (Track A finished and committed to the log before
  Track B's acquisition started, per the task's explicit ordering).

**Real results:**
- **Track A**: all 15 real HAMO observations sit at -13° to -29°
  latitude. The one well-established, highly-cited compositional
  boundary in Dawn VIR literature (De Sanctis et al.) — diogenite
  concentrated near the south pole (Rheasilvia, ~72°S), eucrite/howardite
  toward the equator — **does not apply to this sample's latitude range
  at all**. A finer named unit (Vestalia Terra, ~34°E) is closer to two
  of the 15 points but is itself described as compositionally mixed at
  the quadrangle scale, and most points are far from it regardless. Could
  not access the actual quadrangle-level published maps (paywalled; the
  one open-access PDF found could not be rendered in this environment —
  no `poppler-utils`). **Honest conclusion: no usable published map at
  these specific 15 coordinates — reported as "no match found," not
  stretched into either direction.**
- **Track B, real LAMO structural findings** (checked before any
  download): HAMO ~12h orbital period vs. LAMO ~4h (Planetary Society
  Dawn Journal, citable) — real, meaningful cadence difference. VIR's
  LAMO cycles 1-3 are genuinely absent from the archive (nominal
  directory 404s); VIR's real "CYCLE4" data is entirely dated 2012-01-08,
  an 8-9 day slip from its nominal 2011-12-31 label; FC's matching real
  window is its own *CYCLE5*, not CYCLE4 — same nominal cycle numbers,
  different real time windows, unlike HAMO.
- **Track B, alignment**: 787 total survivors on combined HAMO+LAMO
  manifests (743 HAMO + 44 new from LAMO), via the unmodified
  `align_dataset()`.
- **Track B, separability (LAMO-only, chosen over combined — states why
  in `month1_log.md`)**: 8 real paired observations, all usable.
  Silhouette k=2/3/4: 0.8740 / 0.6175 / 0.5192. **Band II values landed
  at almost exactly HAMO's same two numbers (~1.957 μm, ~2.164 μm) —
  not just "also bimodal," numerically matching to ~0.001 μm across two
  independent mission phases.** This is reported as a new, real, open
  concern: possible band-center-fitting quantization artifact, not
  previously considered, not resolved here.
- **Track B, confound check**: 7 of 8 LAMO observations split into two
  real sessions ~4.3h apart (matching LAMO's own orbital period) — but
  the single "≈2.164" observation was acquired 4 minutes after, and at a
  geographically adjacent location to, a "≈1.957" neighbor in the *same*
  session, not a separate one. That's a real structural difference from
  HAMO's pattern (weak evidence *against* the session-confound
  generalizing here) — weak because n=1, and because the exact-value
  recurrence keeps the quantization-artifact explanation equally open.
- **Bottom line, stated in month1_log.md**: three live hypotheses remain
  open (session confound / genuine localized composition / quantization
  artifact); neither track resolves the question, both narrow it. No
  labeling or class assignment attempted, per explicit scope.

**Verified how:**
- WebSearch for Track A, cross-checked across multiple independent
  result summaries citing De Sanctis et al.'s Dawn VIR Vesta mineralogy
  papers and Rheasilvia/Vestalia Terra coordinates (Wikipedia, sourced
  to the IAU gazetteer); attempted direct fetch of an open-access arXiv
  PDF and the A&A 2021 paper (both blocked — 403 on A&A via both
  WebFetch and a browser-UA curl retry; the arXiv PDF fetched but could
  not be rendered by the `Read` tool, `poppler-utils` missing) — reported
  as a genuine access limitation rather than silently dropped.
- Fetched real FC/VIR LAMO directory listings directly (`curl`, browser
  UA) before adding anything to `config.yaml` — did not assume LAMO's
  naming mirrored HAMO's.
- Diagnosed the real 168/336 FC 404 failures by inspecting the actual
  failing URLs, confirming server-side (via direct `curl` HEAD/GET
  checks) that both a `.FIT`-under-`/DATA/FITS/` and a
  `.IMG`-under-`/DATA/IMG/` file genuinely exist for the same product,
  and confirming via direct INDEX.TAB inspection that every non-`.LBL`
  row has an exact `.LBL`-row sibling for the same `PRODUCT_ID` in this
  window (168 non-.LBL rows, 168 matching .LBL rows, 0 orphaned) before
  writing the fix — not assumed.
- Re-ran the fixed acquisition (168/168 downloaded, 0 failures) and
  spot-checked one specific product's final manifest entry to confirm it
  resolved to the correct FITS-format label+data pair, not the
  IMG-as-label mistake.
- `python -m pytest tests/ -q`: 33/33 passing after the
  `pds_acquisition.py` fix.
- Re-ran `align_dataset()` (unmodified) and read its real log output
  directly for the 787-survivor figure.
- Reused `scripts/audit_band_separability.py`'s own functions
  (imported, not re-implemented) against a LAMO-only filtered copy of
  `sample_metadata.csv` — the script file itself was not modified.

**Open issues / blockers:**
- **Go/no-go: unchanged from Session 3 — still not ready for labeling**,
  now for an even more specific reason: three competing explanations for
  the observed bimodality remain open, and this task's own findings
  raised a brand-new one (quantization artifact) rather than closing any
  existing one down. A follow-up conversation needs to decide which to
  investigate next — this session does not recommend one over the
  others.
- **`ml/data/pds_acquisition.py`'s FC row-filtering fix is scoped to the
  specific `.LBL`-vs-`.IMG` row duplication found in this LAMO volume** —
  it has not been checked against every other phase/volume in the
  archive, so a similar issue could in principle recur elsewhere and go
  uncaught until it does.
- The Track A literature search could not access the actual published
  quadrangle-level compositional maps (paywalled + a PDF-rendering tool
  gap in this environment) — if that access is ever available, Track A
  should be redone with real map figures, not just search-result
  summaries of them.

**Branch/commit:** `month1-data-pipeline`, this entry's own commit (see
`git log` on this branch — "Month 1 Slice 11"), pushed: yes.

---

## Session 5 — 2026-09-10

**Task attempted:** Test the one new hypothesis Session 4 raised but did
not investigate — that the recurring HAMO/LAMO Band II bimodality
(~1.957 μm / ~2.164 μm) is a fitting/quantization artifact of
`compute_band_center()`, not real geology. Diagnosis only, by explicit
instruction: `ml/data/spatial_alignment.py`, `ml/utils/splits.py`, the
specificity penalty, `ml/data/pds_acquisition.py`, and
`compute_band_center()` itself were all off-limits (confirmed untouched
below). No labeling or class assignment attempted.

**What actually changed:**

- `docs/month1_log.md` — new "Slice 12" section with the full evidence
  chain and verdict.
- `docs/handoff/artifacts/band_ii_raw_overlay.png` — new artifact: 3
  stacked plots of real, unfitted `mean_spectrum` values across
  `BAND_II_WINDOW_UM` for 2 within-cluster HAMO pairs and the LAMO
  cross-session pair.
- This entry.
- No source files changed. `ml/data/spectral_labeling.py` (which holds
  `compute_band_center()`) was read extensively but not edited.

**Real results:**

- Real IR grid (`BAND_BIN_CENTER`, `BAND_II_WINDOW_UM` slice): 90 points,
  spacing 0.0090-0.0100 μm (mean 0.00945 μm) — confirms the ~0.0095 μm
  suspicion; coarse enough, relative to Vesta's broad Band II feature,
  that the hypothesis is plausible on its face, not ruled out by grid
  spacing alone.
- Numeric (not just visual) comparison of the 6 real spectra behind the
  3 comparison pairs: all 6 share the same set of near-tied competing
  local minima (1.957, 1.995, 2.014, 2.165, sometimes 2.146 μm) in their
  continuum-removed curves, differing only in which one is marginally
  lowest (typically <2% relative depth apart). The raw curves do not
  show genuinely different absorption-minimum shapes.
- Perturbation test on one real spectrum (clock 370705798, unmodified
  `compute_band_center()`): sub-grid wavelength shifts alone produced
  smooth output (1.95721 → 1.96624 μm across a full grid step, no jump).
  Additive Gaussian noise at realistic amplitude (0.5-2% of mean signal,
  10 seeds each) caused the reported center to discretely jump between
  ≈1.957 μm and ≈2.164/2.165 μm — the exact two real cluster values —
  with no compositional change to the input.
- Source read confirmed 3 raw-grid-value fallback paths in
  `compute_band_center()` (edge-of-window, degenerate parabola,
  non-parabolic fit) plus a 4th, `if not (x0 <= vertex <= x2): return
  float(x1)`, that discards the fit whenever the vertex falls outside
  its own 3-point window — real code, but confirmed NOT the operative
  mechanism for these 6 spectra's base fits (`vertex_inside_window` was
  `True` in all 6); the operative mechanism is the upstream global-
  argmin selection among near-degenerate local minima.
- **Verdict written into `docs/month1_log.md`, Slice 12: SUPPORTED.**
  Stated plainly with its real limitation: this does not prove there is
  no genuine compositional signal underneath, only that the current
  fitting method cannot be trusted to report it cleanly given its
  demonstrated noise sensitivity.

**Verified how:**

- Every number above was computed directly against real QUBE data via
  `read_vir_qube()` (unmodified) and the identical continuum-removal math
  used inside `compute_band_center()`, not asserted.
- The perturbation test called the real, unmodified
  `compute_band_center()` function (imported, never edited) on real
  spectra with synthetic shifts/noise applied only to local copies of
  the arrays passed in.
- `git diff --stat` confirmed zero changes to `ml/data/spatial_alignment.py`,
  `ml/utils/splits.py`, `ml/data/pds_acquisition.py`, and
  `ml/data/spectral_labeling.py` before committing.
- `python -m pytest tests/ -q`: 33/33 passing (no protected/tested code
  changed, run as a regression sanity check anyway).

**Open issues / blockers:**

- **Go/no-go: still not ready for labeling.** This session narrows,
  rather than closes, the question: the quantization-artifact hypothesis
  is now evidence-backed, but a real compositional signal could still
  exist underneath a noise-sensitive fit — this session does not and
  cannot distinguish "no real signal" from "real signal masked by fit
  instability."
  Recommended concrete follow-up (not started here, per scope): give
  `compute_band_center()` a near-tie/ambiguity flag (or widen/smooth the
  fit window) and re-run the Slice 10/11 separability and confound
  checks before any labeling decision.
- The perturbation test used one real base spectrum (370705798) and
  synthetic noise/shift models (Gaussian, uniform sub-grid shift) — it
  has not been repeated across all 6 spectra or validated against VIR's
  actual documented instrument-noise characteristics, so the specific
  jump rates (e.g. "2 of 10 seeds at 0.5%") are illustrative of the
  mechanism, not a calibrated false-bimodality rate.

**Branch/commit:** `month1-data-pipeline`, this entry's own commit (see
`git log` on this branch — "Month 1 Slice 12"), pushed: yes.
