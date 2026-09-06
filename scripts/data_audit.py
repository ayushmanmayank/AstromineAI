"""
Month 1 Slice 3, Part A — data audit over datasets/metadata/sample_metadata.csv.

Reports (honestly, including the N=0 case rather than crashing or
pretending there's a distribution to describe):
  - total surviving pairs
  - correspondence_confidence distribution (min/median/max + histogram)
  - spatial distribution of surviving regions (clustered vs spread)
  - time-of-observation spread across mission phases

Read-only: does not touch datasets/metadata/sample_metadata.csv.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ml.utils.metadata_schema import read_metadata_csv  # noqa: E402


def mission_phase_from_time(iso_time: str) -> str:
    """Bucket a START_TIME string into a Dawn Vesta mission-phase label by
    date range. Dawn's own MISSION_PHASE_NAME field (in the FC/VIR labels)
    is the authoritative source per-product; this is a coarse fallback for
    aggregate reporting keyed only on date.
    """
    if not iso_time:
        return "UNKNOWN"
    date_part = iso_time[:10] if "-" in iso_time[:5] else None
    # Dawn Vesta phase boundaries (approximate, from mission timeline):
    phases = [
        ("2011-05-03", "2011-06-30", "APPROACH"),
        ("2011-07-01", "2011-08-10", "SURVEY"),
        ("2011-08-11", "2011-09-28", "HAMO_1"),
        ("2011-09-29", "2011-12-11", "LAMO"),
        ("2011-12-12", "2012-06-14", "HAMO_2"),
        ("2012-06-15", "2012-09-05", "TRANSFER_TO_CERES"),
    ]
    if date_part:
        for lo, hi, name in phases:
            if lo <= date_part <= hi:
                return name
    return "OTHER/UNKNOWN"


def main() -> int:
    csv_path = REPO_ROOT / "datasets" / "metadata" / "sample_metadata.csv"
    records = read_metadata_csv(csv_path)
    n = len(records)

    print(f"=== Month 1 Data Audit — {csv_path.relative_to(REPO_ROOT)} ===")
    print(f"Total surviving pairs: {n}")

    if n == 0:
        print()
        print("N=0: there is nothing to compute a confidence distribution, spatial")
        print("distribution, or time-of-observation spread over. This is reported")
        print("plainly rather than fabricated or skipped — see docs/month1_log.md")
        print("for why (Slice 2's real geometry/time-window findings).")
        print()
        print("VERDICT: cannot support ANY model comparison (3-way or otherwise) —")
        print("there are zero labeled training examples.")
        return 0

    df = pd.DataFrame([r.__dict__ for r in records])

    print()
    print("--- correspondence_confidence distribution ---")
    conf = df["correspondence_confidence"]
    print(f"min={conf.min():.3f}  median={conf.median():.3f}  max={conf.max():.3f}")
    bins = np.linspace(0, 1, 11)
    hist, edges = np.histogram(conf, bins=bins)
    for count, lo, hi in zip(hist, edges[:-1], edges[1:]):
        print(f"  [{lo:.1f}, {hi:.1f}): {count}")

    print()
    print("--- spatial distribution (region centers) ---")
    lat_range = df["center_latitude"].max() - df["center_latitude"].min()
    lon_range = df["center_longitude"].max() - df["center_longitude"].min()
    print(f"latitude span: {lat_range:.1f} deg, longitude span: {lon_range:.1f} deg")
    # Coarse clustering check: how many distinct 10-degree bins are occupied?
    lat_bins = (df["center_latitude"] // 10).nunique()
    lon_bins = (df["center_longitude"] // 10).nunique()
    print(f"occupies {lat_bins} distinct 10-degree latitude bins, {lon_bins} longitude bins")

    print()
    print("--- time-of-observation spread ---")
    df["mission_phase"] = df["image_start_time"].apply(mission_phase_from_time)
    print(df["mission_phase"].value_counts().to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())
