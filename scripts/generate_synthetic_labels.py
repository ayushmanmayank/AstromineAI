"""
Month 2 engineering pipeline: generate a SYNTHETIC labeled dataset for
end-to-end pipeline validation (training / evaluation / explainability /
serving), independent of whatever Track A's real-compositional-signal
investigation on month1-data-pipeline concludes.

THIS DOES NOT PRODUCE REAL SCIENCE LABELS. It exists only to prove the
mechanics of train.py / evaluate.py / splits.py / the backend / the
frontend work end-to-end on some concrete labeled dataset, since as of
this branch's creation the real dataset (datasets/metadata/
sample_metadata.csv) has zero real compositional labels assigned
(all rows are label="unlabeled").

What this script does, precisely (so the process is fully disclosed and
auditable, not just asserted "random"):
  1. Reads the real, unmodified sample_metadata.csv (787 real aligned
     FC-image/VIR-spectrum crops, 50 unique real VIR spectra) -- read-only,
     never written back to.
  2. Assigns one synthetic label per UNIQUE real spectrum_product_id (not
     per crop), via a seeded uniform-random draw over the same 3-class
     vocabulary ml/data/dataset.py's VestaDataset already expects
     (diogenite_like / howardite_like / eucrite_like), so every crop of
     the same real spectrum gets the same synthetic label -- this mirrors
     how a real label (which is a property of the spectrum, not the crop)
     would eventually be assigned, rather than handing every crop an
     independent coin flip that would make the synthetic dataset visibly
     nonsensical to anyone who inspects it later.
  3. Sets label_source on every row to a string prefixed
     "SYNTHETIC_DEMO -- not a real compositional label", naming the exact
     seed and rule, so this can never be mistaken for a real,
     scientifically-derived label downstream (metadata_schema.py's
     validate() also requires every label_source to be specific and
     >=8 chars -- this clears that bar honestly, not by accident).
  4. Runs the real, UNMODIFIED assign_region_based_splits() from
     ml/utils/splits.py on the result, using this project's existing
     configs/config.yaml split fractions/seed/bin size -- a real
     train/val/test split, on synthetic labels.
  5. Writes the result to datasets/metadata/sample_metadata_SYNTHETIC.csv
     -- a new file. datasets/metadata/sample_metadata.csv (the real file)
     is never opened for writing by this script.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.data.dataset import CLASSES  # noqa: E402 -- reuse the real class vocabulary, don't redefine it
from ml.utils.metadata_schema import read_metadata_csv, write_metadata_csv  # noqa: E402
from ml.utils.splits import assign_region_based_splits  # noqa: E402

logger = logging.getLogger("generate_synthetic_labels")

SYNTHETIC_LABEL_SEED = 42
SYNTHETIC_LABEL_SOURCE_PREFIX = "SYNTHETIC_DEMO -- not a real compositional label"

REAL_METADATA_CSV = "datasets/metadata/sample_metadata.csv"
SYNTHETIC_METADATA_CSV = "datasets/metadata/sample_metadata_SYNTHETIC.csv"


def assign_synthetic_labels(records: list, seed: int = SYNTHETIC_LABEL_SEED) -> dict[str, str]:
    """Mutates `records` in place, setting .label and .label_source.
    Returns {spectrum_product_id: assigned_label} for logging/auditing."""
    rng = random.Random(seed)
    unique_spectra = sorted({r.spectrum_product_id for r in records})
    label_by_spectrum = {spec: rng.choice(CLASSES) for spec in unique_spectra}

    source = (
        f"{SYNTHETIC_LABEL_SOURCE_PREFIX} -- uniform random over {CLASSES}, "
        f"seed={seed}, one draw per unique spectrum_product_id "
        f"(propagated to every crop of that spectrum)"
    )
    for record in records:
        record.label = label_by_spectrum[record.spectrum_product_id]
        record.label_source = source

    return label_by_spectrum


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--real-csv", default=REAL_METADATA_CSV)
    parser.add_argument("--out-csv", default=SYNTHETIC_METADATA_CSV)
    parser.add_argument("--seed", type=int, default=SYNTHETIC_LABEL_SEED)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")

    if Path(args.out_csv).resolve() == Path(args.real_csv).resolve():
        raise ValueError("Refusing to write the synthetic dataset over the real metadata CSV.")

    records = read_metadata_csv(args.real_csv)
    logger.info("Read %d real rows from %s (real data, real crops -- labels are the only synthetic part)", len(records), args.real_csv)
    if not records:
        logger.error("0 rows in %s -- nothing to synthesize labels for.", args.real_csv)
        return 1

    label_by_spectrum = assign_synthetic_labels(records, seed=args.seed)
    counts: dict[str, int] = {c: 0 for c in CLASSES}
    for label in label_by_spectrum.values():
        counts[label] += 1
    logger.info(
        "Assigned SYNTHETIC labels to %d unique real spectra (seed=%d): %s",
        len(label_by_spectrum), args.seed, counts,
    )

    with open(args.config, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    split_cfg = config["data"]["splits"]
    assign_region_based_splits(
        records,
        train_frac=split_cfg["train"],
        val_frac=split_cfg["val"],
        test_frac=split_cfg["test"],
        seed=split_cfg["seed"],
        bin_size_degrees=split_cfg["bin_size_degrees"],
    )

    write_metadata_csv(records, args.out_csv)
    logger.info(
        "Wrote %d rows (SYNTHETIC labels, real splits) to %s. "
        "Real file %s was never opened for writing.",
        len(records), args.out_csv, args.real_csv,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
