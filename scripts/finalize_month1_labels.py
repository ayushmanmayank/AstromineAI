"""
Month 1 Slice 3, Part C — assign labels + region-based splits to
datasets/metadata/sample_metadata.csv, in place.

Pipeline: read_metadata_csv -> label_sample_metadata (VIR-only, Part B
scheme) -> assign_region_based_splits (config-driven fractions) ->
write_metadata_csv (validates every row; will refuse to write an
inconsistent or generically-sourced label).
"""

from __future__ import annotations

import logging
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ml.data.spectral_labeling import label_sample_metadata  # noqa: E402
from ml.utils.metadata_schema import read_metadata_csv, write_metadata_csv  # noqa: E402
from ml.utils.splits import assign_region_based_splits  # noqa: E402

logger = logging.getLogger("finalize_month1_labels")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")

    with open(REPO_ROOT / "configs" / "config.yaml", "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    csv_path = REPO_ROOT / "datasets" / "metadata" / "sample_metadata.csv"
    records = read_metadata_csv(csv_path)
    print(f"Loaded {len(records)} records from {csv_path.relative_to(REPO_ROOT)}")

    records = label_sample_metadata(records)

    label_counts = Counter(r.label for r in records)
    print(f"Class balance after labeling ({len(records)} records): {dict(label_counts)}")

    split_cfg = config["data"]["splits"]
    records = assign_region_based_splits(
        records,
        train_frac=split_cfg["train"],
        val_frac=split_cfg["val"],
        test_frac=split_cfg["test"],
        seed=split_cfg["seed"],
        bin_size_degrees=split_cfg["bin_size_degrees"],
    )

    split_counts = Counter(r.split for r in records)
    print(f"Split assignment: {dict(split_counts)}")

    per_split_class = Counter((r.split, r.label) for r in records)
    print("Per-split, per-class counts:")
    for (split, label), count in sorted(per_split_class.items()):
        print(f"  {split:10s} {label:30s} {count}")

    write_metadata_csv(records, csv_path)
    print(f"Wrote {len(records)} validated records back to {csv_path.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
