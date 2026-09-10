"""
Month 1 Slice 13 -- re-run of scripts/audit_band_separability.py's
separability analysis using compute_band_center_v2() (the fix for the
instability Slice 12 diagnosed in compute_band_center()) instead of the
original method.

This is a NEW file, not an edit of audit_band_separability.py -- that
script (and every ml/ module it reuses read-only) is left completely
untouched, so the old and new analyses can be run and compared side by
side. Reuses pair_observations_by_clock() from the original script
unmodified (import, not copy) so both scripts pair observations
identically; only the band-center extraction step is swapped out.

Both Band I and Band II centers use compute_band_center_v2() here (not
just Band II) for internal consistency -- the corrected dataset should
not mix an old-method Band I value with a new-method Band II value in
the same 2D clustering point. Slice 12 only diagnosed the instability via
Band II data, but the mechanism (compute_band_center()'s single-argmin,
narrow-parabola fit) is identical code for both bands.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_band_separability import pair_observations_by_clock, silhouette_by_k  # noqa: E402
from ml.data.spectral_labeling import (  # noqa: E402
    BAND_I_DEPTH_FLOOR,
    BAND_I_WINDOW_UM,
    BAND_II_DEPTH_FLOOR,
    BAND_II_WINDOW_UM,
    compute_band_center_v2,
    compute_band_depth,
    read_vir_qube,
)


def extract_band_points_v2(paired: pd.DataFrame) -> pd.DataFrame:
    """Same role as audit_band_separability.extract_band_points(), but
    using compute_band_center_v2() for the center-wavelength fit. Depth
    gating (BAND_*_DEPTH_FLOOR) is unchanged -- that is a data-quality
    gate on compute_band_depth(), which is not touched by this task."""
    rows = []
    for _, r in paired.iterrows():
        vis = read_vir_qube(r["vis_label_path"])
        ir = read_vir_qube(r["ir_label_path"])

        band_i_center = band_ii_center = None
        band_i_depth = band_ii_depth = None
        band_i_ambiguous = band_ii_ambiguous = None
        band_i_confidence = band_ii_confidence = None
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
                res = compute_band_center_v2(vis.wavelengths_um, vis.mean_spectrum, *BAND_I_WINDOW_UM)
                if res is None:
                    reason.append("Band I center unfittable")
                else:
                    band_i_center = res.center_um
                    band_i_ambiguous = res.ambiguous
                    band_i_confidence = res.confidence

        if ir is None:
            reason.append("IR cube unreadable")
        elif not ir.is_calibrated:
            reason.append("IR product not calibrated (RDR)")
        else:
            band_ii_depth = compute_band_depth(ir.wavelengths_um, ir.mean_spectrum, *BAND_II_WINDOW_UM)
            if band_ii_depth is None or band_ii_depth < BAND_II_DEPTH_FLOOR:
                reason.append(f"Band II depth {band_ii_depth} below floor {BAND_II_DEPTH_FLOOR}")
            else:
                res = compute_band_center_v2(ir.wavelengths_um, ir.mean_spectrum, *BAND_II_WINDOW_UM)
                if res is None:
                    reason.append("Band II center unfittable")
                else:
                    band_ii_center = res.center_um
                    band_ii_ambiguous = res.ambiguous
                    band_ii_confidence = res.confidence

        usable = band_i_center is not None and band_ii_center is not None
        rows.append({
            "clock": r["clock"],
            "band_i_center_um": band_i_center,
            "band_ii_center_um": band_ii_center,
            "band_i_depth": band_i_depth,
            "band_ii_depth": band_ii_depth,
            "band_i_ambiguous": band_i_ambiguous,
            "band_ii_ambiguous": band_ii_ambiguous,
            "band_i_confidence": band_i_confidence,
            "band_ii_confidence": band_ii_confidence,
            "usable": usable,
            "reason": "; ".join(reason) if reason else "",
        })
    return pd.DataFrame(rows)


def main() -> int:
    metadata_csv = REPO_ROOT / "datasets" / "metadata" / "sample_metadata.csv"
    paired = pair_observations_by_clock(metadata_csv)
    print(f"Paired observations (VIS+IR by clock count), HAMO set: {len(paired)}")

    band_points = extract_band_points_v2(paired)
    print()
    print(band_points.to_string(index=False))

    usable = band_points[band_points["usable"]]
    print()
    print(f"Usable (both bands fit the depth gate) 2D points: {len(usable)} of {len(paired)}")
    n_ambiguous_ii = int(usable["band_ii_ambiguous"].sum())
    n_ambiguous_i = int(usable["band_i_ambiguous"].sum())
    print(f"Band II ambiguous (v2 flag): {n_ambiguous_ii} of {len(usable)}")
    print(f"Band I ambiguous (v2 flag): {n_ambiguous_i} of {len(usable)}")

    if len(usable) < 3:
        print("Too few usable points for any clustering analysis.")
        return 0

    points = usable[["band_i_center_um", "band_ii_center_um"]].to_numpy()
    sil = silhouette_by_k(points)
    print()
    print("Silhouette scores (KMeans, random_state=42), v2 method:")
    for k, score in sil.items():
        print(f"  k={k}: {score}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
