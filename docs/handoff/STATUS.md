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
