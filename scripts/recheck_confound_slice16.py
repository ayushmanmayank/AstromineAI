"""
Month 1 Slice 16 -- the bounded, final acquisition attempt (2 new HAMO
cycles + 1 new denser LAMO window) to try to break the acquisition-
session and fit-confidence confounds found in Slices 10-15. Re-runs the
phase-separated v2 silhouette, session-confound, and confidence-confound
checks (matching Slice 15's structure) on this larger real combined
sample.

New file, read-only with respect to every existing module/script: reuses
pair_observations_by_clock()/confound_summary()/silhouette_by_k() from
audit_band_separability.py, extract_band_points_v2() from
audit_band_separability_v2.py, and assign_sessions() from
recheck_confound_v2.py -- all unmodified imports.

Mission-phase classification note: earlier slices classified HAMO vs
LAMO by clock-count string prefix ("370.../379..."), which only worked
because just two narrow acquisition windows existed. This slice's new
windows have real clock counts starting with "372"/"373" (new HAMO
cycles) and "387" (new LAMO window) -- prefix matching would silently
misclassify them. Classifying instead by the real, unambiguous
"_HAMO"/"_LAMO" substring in each observation's real spectrum_label_path
(present in every real PDS3 VIR label path regardless of which cycle),
checked directly against the real paths before relying on it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu
from sklearn.cluster import KMeans

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_band_separability import confound_summary, pair_observations_by_clock, silhouette_by_k  # noqa: E402
from scripts.audit_band_separability_v2 import extract_band_points_v2  # noqa: E402
from scripts.recheck_confound_v2 import assign_sessions  # noqa: E402


def classify_mission_phase(ir_label_path: str) -> str:
    p = str(ir_label_path)
    if "_HAMO" in p:
        return "HAMO"
    if "_LAMO" in p:
        return "LAMO"
    return "UNKNOWN"


def analyze_phase(name: str, paired_phase: pd.DataFrame) -> dict:
    print(f"\n{'=' * 70}\n{name} (n={len(paired_phase)})\n{'=' * 70}")
    band_points = extract_band_points_v2(paired_phase)
    usable = band_points[band_points["usable"]].reset_index(drop=True)
    print(f"Usable (v2, both bands fit the depth gate): {len(usable)} of {len(paired_phase)}")
    if len(usable) < 4:
        print("Too few usable points for clustering.")
        return {}

    points = usable[["band_i_center_um", "band_ii_center_um"]].to_numpy()
    sil = silhouette_by_k(points)
    print("Silhouette (KMeans, random_state=42):", sil)

    labels = KMeans(n_clusters=2, random_state=42, n_init=10).fit_predict(points)
    usable = usable.copy()
    usable["cluster"] = labels
    print("k=2 cluster sizes:", usable["cluster"].value_counts().to_dict())

    paired_usable = paired_phase[paired_phase["clock"].isin(usable["clock"])].set_index("clock").loc[usable["clock"]].reset_index()
    confound_df, angle_summary = confound_summary(paired_usable, labels)
    print("\nPer-cluster geography/illumination:")
    print(angle_summary.to_string())

    sessioned = assign_sessions(confound_df)
    session_majority = sessioned.groupby("session_id")["cluster"].agg(lambda s: s.value_counts().idxmax())
    sessioned["session_majority_cluster"] = sessioned["session_id"].map(session_majority)
    sessioned["matches_session_majority"] = sessioned["cluster"] == sessioned["session_majority_cluster"]
    n_match = int(sessioned["matches_session_majority"].sum())
    n_total = len(sessioned)
    n_sessions = sessioned["session_id"].nunique()
    print(f"\nSession-confound match: {n_match} of {n_total} ({100*n_match/n_total:.1f}%), {n_sessions} real sessions")

    c0 = usable[usable["cluster"] == 0]["band_ii_confidence"]
    c1 = usable[usable["cluster"] == 1]["band_ii_confidence"]
    print(f"\nConfidence by cluster: cluster0 (n={len(c0)}) median={c0.median():.4f}, cluster1 (n={len(c1)}) median={c1.median():.4f}")
    conf_p = None
    if len(c0) >= 2 and len(c1) >= 2:
        _, conf_p = mannwhitneyu(c0, c1, alternative="two-sided")
        print(f"Mann-Whitney U p-value: {conf_p:.4g}")

    return {
        "n": len(usable), "silhouette": sil, "session_match": (n_match, n_total, n_sessions),
        "confidence_p": conf_p, "cluster_sizes": usable["cluster"].value_counts().to_dict(),
    }


def main() -> int:
    metadata_csv = REPO_ROOT / "datasets" / "metadata" / "sample_metadata.csv"
    paired = pair_observations_by_clock(metadata_csv)
    print(f"Total real paired observations (all mission phases, all cycles/windows): {len(paired)}")

    # Classify mission phase via real label path substring (see module docstring).
    def get_phase(row):
        return classify_mission_phase(row["ir_label_path"])
    paired = paired.copy()
    paired["mission_phase"] = paired.apply(get_phase, axis=1)
    print("Mission-phase breakdown:", paired["mission_phase"].value_counts().to_dict())

    hamo = paired[paired["mission_phase"] == "HAMO"].reset_index(drop=True)
    lamo = paired[paired["mission_phase"] == "LAMO"].reset_index(drop=True)
    unknown = paired[paired["mission_phase"] == "UNKNOWN"]
    if len(unknown) > 0:
        print(f"WARNING: {len(unknown)} observations could not be classified HAMO/LAMO -- excluded from phase-separated analysis:")
        print(unknown[["clock", "ir_label_path"]].to_string(index=False))

    hamo_result = analyze_phase("HAMO (all cycles combined)", hamo)
    lamo_result = analyze_phase("LAMO (all windows combined)", lamo)

    # Mission-phase confound check on the combined sample (same style as Slice 14),
    # for reference only -- primary analysis is phase-separated above.
    print(f"\n{'=' * 70}\nCombined (for reference only, phase-mixing confound expected per Slice 14)\n{'=' * 70}")
    combined = pd.concat([hamo, lamo], ignore_index=True)
    band_points = extract_band_points_v2(combined)
    usable = band_points[band_points["usable"]].reset_index(drop=True)
    if len(usable) >= 4:
        points = usable[["band_i_center_um", "band_ii_center_um"]].to_numpy()
        sil = silhouette_by_k(points)
        print("Combined silhouette:", sil)
        labels = KMeans(n_clusters=2, random_state=42, n_init=10).fit_predict(points)
        usable = usable.copy()
        usable["cluster"] = labels
        usable["mission_phase"] = combined.set_index("clock").loc[usable["clock"], "mission_phase"].values
        table = pd.crosstab(usable["mission_phase"], usable["cluster"])
        print(table)
        if table.shape == (2, 2):
            odds, p = fisher_exact(table.values)
            print(f"Fisher exact (mission x cluster): odds={odds:.3f} p={p:.4g}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
