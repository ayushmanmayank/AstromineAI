# Scientific Integrity Checklist

Non-negotiable constraints for all data work in this project. Every Month 1
slice must be checked against this list before being marked done.

## Data provenance

- [ ] Every downloaded product retains its **original PDS metadata**:
      mission, instrument, dataset ID, observation time, and geometry
      reference. `.LBL` (label) files are never discarded, even after
      derived products are produced from the data they describe.
- [ ] No URL is hardcoded into config or code until it has been **verified
      to resolve and to actually serve the claimed data** (right target
      body, right instrument, right mission phase). Do not guess at PDS
      paths by pattern-matching another mission's layout.
- [ ] The specific PDS node, dataset ID, and volume ID for every source is
      recorded in `configs/config.yaml` and in the relevant month log —
      not just a home-page URL.

## Process discipline

- [ ] Each Month 1 slice implements only what it claims to. Spatial
      alignment, labeling, and dataset splitting are separate slices and
      are not implemented early "while we're in there."
- [ ] Small-sample (`--limit`) runs are used to validate a pipeline stage
      before a full pull is attempted.
- [ ] Progress logs (`docs/month1_log.md`, etc.) reflect what was
      **actually run and confirmed**, not what was planned or assumed.

## Reproducibility

- [ ] Config values (URLs, dataset IDs) are the single source of truth —
      scripts read from config rather than embedding literals.
- [ ] Downloads are idempotent: re-running a fetch step does not corrupt
      or silently duplicate already-verified local data.
