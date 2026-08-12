"""LacTiC program ratings — strength, development trajectory, and tiers.

Built on the meet-adjusted athlete ratings:
  * program strength  = mean adjusted pace of a team's top-5 runners per season
  * trajectory        = OLS slope of program pace over seasons (faster = improving)
  * ranking           = most-recent-season program strength
  * tiers             = KMeans over (current strength, trajectory) -> 3 tiers
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from d3xc.lactic.ratings import compute_athlete_ratings
from d3xc.analyze.metrics import load_frames

N_SCORERS = 5


def program_strength(athlete_ratings: pd.DataFrame) -> pd.DataFrame:
    """Top-5 mean adjusted pace + within-season program rating (0-100)."""
    rows = []
    for (team, conf, gender, season), grp in athlete_ratings.groupby(
        ["team", "conference", "gender", "season"]
    ):
        paces = grp["adj_pace_sec_per_km"].sort_values().tolist()
        if len(paces) < N_SCORERS:
            continue
        rows.append({
            "team": team, "conference": conf, "gender": gender, "season": season,
            "program_adj_pace": float(np.mean(paces[:N_SCORERS])),
            "n_scorers": len(paces),
        })
    strength = pd.DataFrame(rows)
    if strength.empty:
        return strength
    # within-season program rating (higher = faster/better)
    def _rate(g):
        mu = g["program_adj_pace"].mean()
        sd = g["program_adj_pace"].std(ddof=0) or 1.0
        g = g.copy()
        g["program_rating"] = 50.0 + 10.0 * (mu - g["program_adj_pace"]) / sd
        return g
    strength = strength.groupby(["gender", "season"], group_keys=False)[
        strength.columns.tolist()
    ].apply(_rate)
    return strength.sort_values(["gender", "season", "program_adj_pace"]).reset_index(drop=True)


def program_trajectory(strength: pd.DataFrame) -> pd.DataFrame:
    """Per (team, gender): OLS slope of program pace vs season.

    `pace_slope` < 0 means getting faster (improving). We also report a
    signed `improvement_rate` = -pace_slope (higher = improving faster).
    """
    rows = []
    for (team, gender, conf), g in strength.groupby(["team", "gender", "conference"]):
        g = g.sort_values("season")
        seasons = g["season"].to_numpy(dtype=float)
        pace = g["program_adj_pace"].to_numpy(dtype=float)
        if len(g) >= 2 and np.ptp(seasons) > 0:
            slope = float(np.polyfit(seasons, pace, 1)[0])
        else:
            slope = 0.0
        rows.append({
            "team": team, "gender": gender, "conference": conf,
            "seasons_tracked": int(len(g)),
            "first_season": int(seasons.min()),
            "last_season": int(seasons.max()),
            "pace_slope": slope,
            "improvement_rate": -slope,
            "latest_adj_pace": float(g.iloc[-1]["program_adj_pace"]),
            "latest_rating": float(g.iloc[-1]["program_rating"]),
        })
    return pd.DataFrame(rows)


def rank_programs(strength: pd.DataFrame, gender: str,
                  season: int | None = None) -> pd.DataFrame:
    """Rank programs by strength (lower adjusted pace = better) for a season."""
    df = strength[strength["gender"] == gender]
    if df.empty:
        return df
    if season is None:
        season = int(df["season"].max())
    df = df[df["season"] == season].sort_values("program_adj_pace")
    df = df.reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)
    return df


def program_tiers(strength: pd.DataFrame, n_tiers: int = 3,
                  random_state: int = 0) -> pd.DataFrame:
    """Cluster programs into tiers using current strength + trajectory.

    Returns one row per (team, gender) with a `tier` (1=strongest cluster) and a
    human-readable `tier_label` plus a `trend` descriptor from the slope sign.
    """
    traj = program_trajectory(strength)
    if traj.empty:
        return traj
    feats = traj[["latest_rating", "improvement_rate"]].to_numpy(dtype=float)
    n_clusters = min(n_tiers, max(1, traj["team"].nunique()))
    if len(traj) < n_clusters or n_clusters < 2:
        traj = traj.copy()
        traj["tier"] = 1
        traj["tier_label"] = "Unclassified"
    else:
        Xs = StandardScaler().fit_transform(feats)
        km = KMeans(n_clusters=n_clusters, n_init=10, random_state=random_state)
        labels = km.fit_predict(Xs)
        traj = traj.copy()
        traj["_cluster"] = labels
        # order clusters by mean latest_rating (desc) -> tier 1 = strongest
        order = (
            traj.groupby("_cluster")["latest_rating"].mean()
            .sort_values(ascending=False).index.tolist()
        )
        tier_map = {c: i + 1 for i, c in enumerate(order)}
        label_names = ["Elite", "Contender", "Developing", "Rebuilding"]
        traj["tier"] = traj["_cluster"].map(tier_map)
        traj["tier_label"] = traj["tier"].map(
            lambda t: label_names[min(t - 1, len(label_names) - 1)]
        )
        traj = traj.drop(columns="_cluster")

    def _trend(slope: float) -> str:
        if slope < -0.3:
            return "Rising"
        if slope > 0.3:
            return "Declining"
        return "Steady"
    traj["trend"] = traj["pace_slope"].map(_trend)
    return traj.sort_values(["tier", "latest_adj_pace"]).reset_index(drop=True)


def load_and_rank(engine=None):
    """Convenience: DB -> athlete ratings -> program strength + tiers."""
    ar = compute_athlete_ratings(load_frames(engine)["results"])
    strength = program_strength(ar)
    return strength, program_tiers(strength)
