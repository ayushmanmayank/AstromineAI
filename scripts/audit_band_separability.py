"""
Month 1 Slice 10, Part 1 — spectral diversity audit + quantitative rigor
additions (silhouette separability check, confound check).

Read-only with respect to every existing ml/ module: reuses
ml.data.spectral_labeling's already-implemented, already-tested QUBE
reader and band-depth/center extraction (Slice 3) and
ml.data.spatial_alignment's generic PDS3 scalar-field regex helpers
(Slice 2) rather than re-implementing or modifying either. Nothing in
ml/ is changed by running this script.

Scope: 743 real surviving image-spectrum pairs (Slice 9) resolve to 30
unique VIR product IDs. VIR's two channels each cover only one
diagnostic band (VIS -> Band I ~0.9-1.0um; IR -> Band II ~1.9-2.0um —
see ml/data/spectral_labeling.py's module docstring), so a real
(Band I center, Band II center) 2D point per *observation* requires
pairing the VIS and IR product for the same real observation by their
shared SPACECRAFT_CLOCK_START_COUNT suffix (e.g. "..._370617178"), not
just eyeballing scattered single-band values.

This script does NOT assign compositional labels. It only asks whether
the real Band I/II measurements show quantitatively defensible
separation into groups -- a prerequisite question for whether labeling
is even statistically supportable at this sample size.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ml.data.spatial_alignment import _get_float, _get_scalar  # noqa: E402 -- generic PDS3 scalar parsers, reused read-only
from ml.data.spectral_labeling import (  # noqa: E402
    BAND_I_DEPTH_FLOOR,
    BAND_I_WINDOW_UM,
    BAND_II_DEPTH_FLOOR,
    BAND_II_WINDOW_UM,
    compute_band_center,
    compute_band_depth,
    read_vir_qube,
)

CLOCK_RE = re.compile(r"_(\d+)$")


def _channel_from_dataset_id(dataset_id: str) -> str:
    if "-VIS-" in dataset_id:
        return "VIS"
    if "-IR-" in dataset_id:
        return "IR"
    raise ValueError(f"Cannot determine VIR channel from dataset_id: {dataset_id!r}")


def pair_observations_by_clock(metadata_csv: str | Path) -> pd.DataFrame:
    """Return one row per real observation (paired VIS+IR product), from
    the unique VIR products referenced in sample_metadata.csv. Products
    that have no same-clock companion in the other channel are reported,
    not silently dropped -- a 2D (Band I, Band II) point needs both.
    """
    df = pd.read_csv(metadata_csv)
    uniq = df.drop_duplicates("spectrum_product_id")[
        ["spectrum_product_id", "spectrum_dataset_id", "spectrum_label_path"]
    ].copy()
    uniq["channel"] = uniq["spectrum_dataset_id"].apply(_channel_from_dataset_id)
    uniq["clock"] = uniq["spectrum_product_id"].apply(lambda pid: CLOCK_RE.search(pid).group(1))

    by_clock = uniq.groupby("clock")
    paired_rows = []
    unpaired = []
    for clock, group in by_clock:
        channels = dict(zip(group["channel"], group["spectrum_label_path"]))
        if "VIS" in channels and "IR" in channels:
            paired_rows.append({"clock": clock, "vis_label_path": channels["VIS"], "ir_label_path": channels["IR"]})
        else:
            unpaired.append((clock, list(channels.keys())))

    if unpaired:
        print(f"WARNING: {len(unpaired)} clock count(s) have only one channel, excluded from pairing: {unpaired}")

    return pd.DataFrame(paired_rows)


def extract_band_points(paired: pd.DataFrame) -> pd.DataFrame:
    """For each real paired observation, extract (band_i_center,
    band_ii_center) using the same functions/thresholds
    ml/data/spectral_labeling.py's classify_spectrum() itself uses --
    calibrated-only, depth-gated. Rows where either band fails the gate
    are marked usable=False, not silently dropped, so the real yield is
    visible."""
    rows = []
    for _, r in paired.iterrows():
        vis = read_vir_qube(r["vis_label_path"])
        ir = read_vir_qube(r["ir_label_path"])

        band_i_center = band_ii_center = None
        band_i_depth = band_ii_depth = None
        reason = []

        if vis is None:
            reason.append("VIS cube unreadable")
        elif not vis.is_calibrated:
            reason.append("VIS product not calibrated (RDR)")
        else:
            band_i_depth = compute_band_depth(vis.wavelengths_um, vis.mean_spectrum, *BAND_I_WINDOW_UM)
            if band_i_depth is None or band_i_depth < BAND_I_DEPTH_FLOOR:
                reason.append(f"Band I depth {band_i_depth} below floor {BAND_I_DEPTH_FLOOR}")
            else:
                band_i_center = compute_band_center(vis.wavelengths_um, vis.mean_spectrum, *BAND_I_WINDOW_UM)
                if band_i_center is None:
                    reason.append("Band I center unfittable")

        if ir is None:
            reason.append("IR cube unreadable")
        elif not ir.is_calibrated:
            reason.append("IR product not calibrated (RDR)")
        else:
            band_ii_depth = compute_band_depth(ir.wavelengths_um, ir.mean_spectrum, *BAND_II_WINDOW_UM)
            if band_ii_depth is None or band_ii_depth < BAND_II_DEPTH_FLOOR:
                reason.append(f"Band II depth {band_ii_depth} below floor {BAND_II_DEPTH_FLOOR}")
            else:
                band_ii_center = compute_band_center(ir.wavelengths_um, ir.mean_spectrum, *BAND_II_WINDOW_UM)
                if band_ii_center is None:
                    reason.append("Band II center unfittable")

        usable = band_i_center is not None and band_ii_center is not None
        rows.append({
            "clock": r["clock"],
            "band_i_center_um": band_i_center,
            "band_ii_center_um": band_ii_center,
            "band_i_depth": band_i_depth,
            "band_ii_depth": band_ii_depth,
            "usable": usable,
            "reason": "; ".join(reason) if reason else "",
        })
    return pd.DataFrame(rows)


def silhouette_by_k(points: np.ndarray, ks=(2, 3, 4), random_state: int = 42) -> dict:
    """Real silhouette scores for k=2,3,4 -- all three reported, not
    cherry-picked. Requires at least k+1 points for a given k (silhouette
    is undefined for k == n_samples)."""
    results = {}
    for k in ks:
        if len(points) <= k:
            results[k] = None
            continue
        labels = KMeans(n_clusters=k, random_state=random_state, n_init=10).fit_predict(points)
        results[k] = silhouette_score(points, labels)
    return results


def confound_summary(paired: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Pull real INCIDENCE_ANGLE/EMISSION_ANGLE/PHASE_ANGLE/START_TIME,
    plus CENTER_LATITUDE/CENTER_LONGITUDE (real ground location -- not
    part of the addendum's required fields, but directly decisive for
    telling "genuinely different terrain" apart from "same terrain,
    spurious time-correlated artifact", and just as cheap to pull with
    the same reused scalar parser) from each observation's VIS label
    (read once here; not read by any existing ml/ module) and summarize
    per assigned cluster."""
    rows = []
    for (_, r), cluster in zip(paired.iterrows(), labels):
        text = Path(r["vis_label_path"]).read_text(encoding="ascii", errors="replace")
        rows.append({
            "clock": r["clock"],
            "cluster": int(cluster),
            "incidence_angle": _get_float(text, "INCIDENCE_ANGLE"),
            "emission_angle": _get_float(text, "EMISSION_ANGLE"),
            "phase_angle": _get_float(text, "PHASE_ANGLE"),
            "center_latitude": _get_float(text, "CENTER_LATITUDE"),
            "center_longitude": _get_float(text, "CENTER_LONGITUDE"),
            "start_time": _get_scalar(text, "START_TIME"),
        })
    df = pd.DataFrame(rows)
    summary = df.groupby("cluster")[
        ["incidence_angle", "emission_angle", "phase_angle", "center_latitude", "center_longitude"]
    ].agg(["min", "median", "max"])
    return df, summary


def main() -> int:
    metadata_csv = REPO_ROOT / "datasets" / "metadata" / "sample_metadata.csv"
    paired = pair_observations_by_clock(metadata_csv)
    print(f"Paired observations (VIS+IR by clock count): {len(paired)}")

    band_points = extract_band_points(paired)
    print()
    print(band_points.to_string(index=False))

    usable = band_points[band_points["usable"]]
    print()
    print(f"Usable (both bands fit the depth gate) 2D points: {len(usable)} of {len(paired)}")

    if len(usable) < 3:
        print("Too few usable points for any clustering analysis.")
        return 0

    points = usable[["band_i_center_um", "band_ii_center_um"]].to_numpy()
    sil = silhouette_by_k(points)
    print()
    print("Silhouette scores (KMeans, random_state=42):")
    for k, score in sil.items():
        print(f"  k={k}: {score}")

    # Use k=2 (the coarsest, most commonly interpretable split for a
    # possible 2-class scheme) as the grouping to check for confounds,
    # regardless of which k scored best -- confound-checking the
    # coarsest split is the most conservative choice.
    labels = KMeans(n_clusters=2, random_state=42, n_init=10).fit_predict(points)
    paired_usable = usable.merge(band_points[["clock"]], on="clock")  # keep same order
    confound_df, summary = confound_summary(
        paired[paired["clock"].isin(usable["clock"])].reset_index(drop=True), labels
    )
    print()
    print("Confound check -- per-cluster (k=2) angle summary:")
    print(summary.to_string())
    print()
    print("Confound check -- per-cluster acquisition times:")
    for cluster in sorted(confound_df["cluster"].unique()):
        times = sorted(confound_df[confound_df["cluster"] == cluster]["start_time"])
        print(f"  cluster {cluster}: {times}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
