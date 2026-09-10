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
