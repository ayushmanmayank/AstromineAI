"""
Month 1 Slice 14 -- does the acquisition-session confound Slice 11 found
(under the old, artifact-affected compute_band_center()) still hold once
Slice 13's fix (compute_band_center_v2()) is applied to the same real
23 combined HAMO+LAMO observations?

New file, read-only with respect to every existing module and script:
reuses pair_observations_by_clock() and confound_summary() from
scripts/audit_band_separability.py (unmodified import) and
extract_band_points_v2() from scripts/audit_band_separability_v2.py
(unmodified import). Neither of those files, nor any ml/ module, is
changed by running this script.

Also checks a new possibility this task's design didn't originally
anticipate: does k=2 cluster assignment correlate with
compute_band_center_v2()'s own ambiguous/confidence output, rather than
(or in addition to) acquisition session?
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_band_separability import confound_summary, pair_observations_by_clock  # noqa: E402
from scripts.audit_band_separability_v2 import extract_band_points_v2  # noqa: E402

# Session-boundary gap threshold. HAMO's own real inter-observation gaps
# are ~9-10 minutes within a session and ~11h44m-12h17m between sessions;
# LAMO's are ~4 minutes within a session and ~4h13m between sessions (see
# Slice 11). Any threshold between ~20 minutes and several hours separates
# both mission phases' real sessions identically -- 30 minutes is chosen
# as a value comfortably inside that gap with no tuning to any particular
# cluster outcome.
SESSION_GAP_THRESHOLD_MINUTES = 30


def _parse_start_time(s: str) -> datetime:
    # Real PDS3 START_TIME format, e.g. "2011-273T01:11:51.748" (day-of-year)
    # or "2012-01-08T11:35:22.123" (calendar date) -- both appear in this
    # project's real labels (see docs/month1_log.md). Try calendar-date
    # first, fall back to day-of-year.
    s = s.strip()
    try:
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        pass
    year = int(s[0:4])
    doy = int(s[5:8])
    rest = s[9:19]
    base = datetime.strptime(f"{year}-{doy:03d}", "%Y-%j")
    h, m, sec = rest.split(":")
    return base.replace(hour=int(h), minute=int(m), second=int(float(sec)))


def assign_sessions(confound_df: pd.DataFrame) -> pd.DataFrame:
    """Real, data-driven session grouping: sort by real START_TIME, start
    a new session whenever the gap since the previous real observation
    exceeds SESSION_GAP_THRESHOLD_MINUTES."""
    df = confound_df.copy()
    df["parsed_time"] = df["start_time"].apply(_parse_start_time)
    df = df.sort_values("parsed_time").reset_index(drop=True)
    session_id = 0
    session_ids = [0]
    for i in range(1, len(df)):
        gap = (df.loc[i, "parsed_time"] - df.loc[i - 1, "parsed_time"]).total_seconds() / 60.0
        if gap > SESSION_GAP_THRESHOLD_MINUTES:
            session_id += 1
        session_ids.append(session_id)
    df["session_id"] = session_ids
    return df


def main() -> int:
    metadata_csv = REPO_ROOT / "datasets" / "metadata" / "sample_metadata.csv"
    paired = pair_observations_by_clock(metadata_csv)
    print(f"Paired observations (VIS+IR by clock count): {len(paired)}")

    band_points = extract_band_points_v2(paired)
    usable = band_points[band_points["usable"]].reset_index(drop=True)
    print(f"Usable (v2, both bands fit the depth gate): {len(usable)} of {len(paired)}")

    points = usable[["band_i_center_um", "band_ii_center_um"]].to_numpy()
    labels = KMeans(n_clusters=2, random_state=42, n_init=10).fit_predict(points)
    usable = usable.copy()
    usable["cluster"] = labels
    print()
    print("=== Step 1: v2 k=2 cluster assignment ===")
    print(usable[["clock", "band_i_center_um", "band_ii_center_um", "band_i_ambiguous",
                  "band_ii_ambiguous", "band_i_confidence", "band_ii_confidence", "cluster"]].to_string(index=False))
    print()
    print("Cluster sizes:", usable["cluster"].value_counts().to_dict())

    # paired rows in the same clock order as `usable`/`labels`, for confound_summary().
    paired_usable = paired[paired["clock"].isin(usable["clock"])].set_index("clock").loc[usable["clock"]].reset_index()
    confound_df, angle_summary = confound_summary(paired_usable, labels)

    print()
    print("=== Step 4 (re-check): per-cluster geography/illumination, v2 clusters ===")
    print(angle_summary.to_string())

    # --- Step 2/3: session grouping + cross-tab against v2 cluster ---
    sessioned = assign_sessions(confound_df)
    sessioned = sessioned.merge(usable[["clock", "cluster"]], on="clock", suffixes=("", "_dup"))
    sessioned["mission"] = sessioned["clock"].apply(lambda c: "HAMO" if c.startswith("370") else "LAMO")

    print()
    print("=== Step 2/3: real session grouping vs v2 cluster ===")
    print(sessioned[["clock", "mission", "start_time", "session_id", "cluster"]].sort_values(["session_id", "start_time"]).to_string(index=False))

    # Per-session majority cluster, and per-observation match/mismatch against it.
    session_majority = sessioned.groupby("session_id")["cluster"].agg(lambda s: s.value_counts().idxmax())
    sessioned["session_majority_cluster"] = sessioned["session_id"].map(session_majority)
    sessioned["matches_session_majority"] = sessioned["cluster"] == sessioned["session_majority_cluster"]

    n_match_all = int(sessioned["matches_session_majority"].sum())
    n_total_all = len(sessioned)
    print()
    print(f"Real cross-tabulation: {n_match_all} of {n_total_all} observations' v2 cluster assignment "
          f"matches their own session's majority cluster.")

    for mission in ["HAMO", "LAMO"]:
        sub = sessioned[sessioned["mission"] == mission]
        n_match = int(sub["matches_session_majority"].sum())
        print(f"  {mission}: {n_match} of {len(sub)} match their session's majority cluster "
              f"({sub['session_id'].nunique()} real sessions)")

    print()
    print("Per-session cluster composition:")
    for sid, grp in sessioned.groupby("session_id"):
        times = ", ".join(sorted(grp["start_time"]))
        clusters = grp["cluster"].tolist()
        print(f"  session {sid} ({grp['mission'].iloc[0]}, n={len(grp)}, {times}): clusters={clusters}")

    # --- Step 5: cluster vs confidence/ambiguity ---
    print()
    print("=== Step 5: v2 cluster vs fit confidence ===")
    conf_summary = usable.groupby("cluster")[["band_i_confidence", "band_ii_confidence"]].agg(["min", "median", "max", "mean"])
    print(conf_summary.to_string())
    amb_summary = usable.groupby("cluster")[["band_i_ambiguous", "band_ii_ambiguous"]].mean()
    print()
    print("Fraction ambiguous per cluster (all should be ~1.0 given Slice 13's 23/23 finding):")
    print(amb_summary.to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())
