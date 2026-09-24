"""
Month 1 Slice 15 -- Slice 14 found that combining HAMO+LAMO into one
n=23 clustering introduced a real mission-phase confound (Fisher exact
odds ratio 14.0, p=0.027) that Slice 10/11's phase-separated analyses
could not detect. This re-runs the v2 (compute_band_center_v2) silhouette
and session-confound analysis SEPARATELY within HAMO (n=15) and within
LAMO (n=8), removing the phase confound by construction rather than by
statistical adjustment.

New file, read-only with respect to every existing module/script: reuses
pair_observations_by_clock() and confound_summary() from
audit_band_separability.py, extract_band_points_v2() from
audit_band_separability_v2.py, and assign_sessions() from
recheck_confound_v2.py -- all unmodified imports. Nothing in ml/ or any
existing script is changed by running this.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.cluster import KMeans

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_band_separability import confound_summary, pair_observations_by_clock, silhouette_by_k  # noqa: E402
from scripts.audit_band_separability_v2 import extract_band_points_v2  # noqa: E402
from scripts.recheck_confound_v2 import assign_sessions  # noqa: E402


def analyze_phase(name: str, paired_phase: pd.DataFrame) -> None:
    print(f"\n{'=' * 70}\n{name} (n={len(paired_phase)})\n{'=' * 70}")

    band_points = extract_band_points_v2(paired_phase)
    usable = band_points[band_points["usable"]].reset_index(drop=True)
    print(f"Usable (v2, both bands fit the depth gate): {len(usable)} of {len(paired_phase)}")
    if len(usable) < 3:
        print("Too few usable points for clustering.")
        return

    points = usable[["band_i_center_um", "band_ii_center_um"]].to_numpy()

    print("\n--- Step 2: silhouette scores (KMeans, random_state=42), phase-separated v2 ---")
    sil = silhouette_by_k(points)
    for k, s in sil.items():
        print(f"  k={k}: {s}")

    # k=2 labels for the confound cross-tabs below.
    labels = KMeans(n_clusters=2, random_state=42, n_init=10).fit_predict(points)
    usable = usable.copy()
    usable["cluster"] = labels
    print(f"\nk=2 cluster sizes: {usable['cluster'].value_counts().to_dict()}")

    paired_usable = paired_phase[paired_phase["clock"].isin(usable["clock"])].set_index("clock").loc[usable["clock"]].reset_index()
    confound_df, angle_summary = confound_summary(paired_usable, labels)

    print("\n--- Step 4 (context): per-cluster geography/illumination ---")
    print(angle_summary.to_string())

    print("\n--- Step 3: real session grouping vs. phase-separated v2 cluster ---")
    # confound_df already carries "cluster" (the same labels passed into
    # confound_summary() above) -- assign_sessions() just adds session_id.
    sessioned = assign_sessions(confound_df)
    print(sessioned[["clock", "start_time", "session_id", "cluster"]].sort_values(["session_id", "start_time"]).to_string(index=False))

    session_majority = sessioned.groupby("session_id")["cluster"].agg(lambda s: s.value_counts().idxmax())
    sessioned["session_majority_cluster"] = sessioned["session_id"].map(session_majority)
    sessioned["matches_session_majority"] = sessioned["cluster"] == sessioned["session_majority_cluster"]
    n_match = int(sessioned["matches_session_majority"].sum())
    n_total = len(sessioned)
    n_sessions = sessioned["session_id"].nunique()
    print(f"\nReal session-confound match: {n_match} of {n_total} "
          f"({100 * n_match / n_total:.1f}%), across {n_sessions} real sessions.")
    print("\nPer-session cluster composition:")
    for sid, grp in sessioned.groupby("session_id"):
        print(f"  session {sid} (n={len(grp)}): clusters={grp['cluster'].tolist()}")

    print("\n--- Step 5: cluster vs. fit confidence, within this phase alone ---")
    c0 = usable[usable["cluster"] == 0]["band_ii_confidence"]
    c1 = usable[usable["cluster"] == 1]["band_ii_confidence"]
    print(f"  cluster 0 (n={len(c0)}): median={c0.median():.4f} mean={c0.mean():.4f}")
    print(f"  cluster 1 (n={len(c1)}): median={c1.median():.4f} mean={c1.mean():.4f}")
    if len(c0) >= 1 and len(c1) >= 1 and (len(c0) + len(c1)) >= 4:
        try:
            stat, p = mannwhitneyu(c0, c1, alternative="two-sided")
            print(f"  Mann-Whitney U p-value: {p:.4f} (n={len(c0)} vs n={len(c1)} -- small-sample caveat applies)")
        except ValueError as exc:
            print(f"  Mann-Whitney U not computable: {exc}")
    else:
        print("  Sample too small per group for a meaningful Mann-Whitney test.")


def main() -> int:
    metadata_csv = REPO_ROOT / "datasets" / "metadata" / "sample_metadata.csv"
    paired = pair_observations_by_clock(metadata_csv)

    hamo = paired[paired["clock"].str.startswith("370")].reset_index(drop=True)
    lamo = paired[paired["clock"].str.startswith("379")].reset_index(drop=True)

    analyze_phase("HAMO-only", hamo)
    analyze_phase("LAMO-only", lamo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
