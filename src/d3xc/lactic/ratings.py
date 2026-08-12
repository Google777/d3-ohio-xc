"""LacTiC runner ratings — meet-adjusted pace via a regularized two-way model.

Cross country times are not comparable across courses/weather/fields. For each
group (by default gender x season) we fit:

    pace_sec_per_km ~= intercept + athlete_effect + meet_effect        (Ridge)

The meet_effect absorbs course difficulty; the athlete_effect is the runner's
true speed. We report each athlete's `adj_pace` = intercept + athlete_effect +
(mean meet_effect) -> their expected pace on a *neutral* course, and a 0-100
`rating` (z-scored within the group so higher = faster).

Ridge regularization keeps ratings stable for athletes/meets with few
observations and resolves the athlete+meet dummy identifiability.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import Ridge
from sklearn.preprocessing import OneHotEncoder

from d3xc.analyze.metrics import load_frames, with_pace

MIN_ATHLETES = 3
MIN_MEETS = 2


def _fit_group(df: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """Return per-athlete adjusted pace for one group of race results.

    Uses sparse one-hot design (athlete + meet dummies) so it scales to the full
    10-year, all-Ohio dataset without materializing a dense matrix.
    """
    meta = (
        df.groupby("athlete_id")
        .agg(
            athlete_name=("athlete_name", "first"),
            team=("team", "first"),
            conference=("conference", "first"),
            races=("pace_sec_per_km", "size"),
        )
    )
    n_meets = df["meet_name"].nunique()
    n_ath = df["athlete_id"].nunique()

    # fallback for sparse groups: plain mean pace, no meet adjustment
    if n_meets < MIN_MEETS or n_ath < MIN_ATHLETES:
        adj = df.groupby("athlete_id")["pace_sec_per_km"].mean()
        meta = meta.join(adj.rename("adj_pace_sec_per_km"))
        meta["meet_adjusted"] = False
        return meta.reset_index()

    enc_a = OneHotEncoder(handle_unknown="ignore")
    enc_m = OneHotEncoder(handle_unknown="ignore")
    A = enc_a.fit_transform(df[["athlete_id"]].astype(str))
    M = enc_m.fit_transform(df[["meet_name"]].astype(str))
    X = sparse.hstack([A, M]).tocsr()
    y = df["pace_sec_per_km"].to_numpy(dtype=float)

    model = Ridge(alpha=alpha, fit_intercept=True)
    model.fit(X, y)

    n_a = A.shape[1]
    a_coefs = model.coef_[:n_a]
    m_coefs = model.coef_[n_a:]
    mean_meet = float(np.mean(m_coefs)) if len(m_coefs) else 0.0
    intercept = float(model.intercept_)

    athlete_ids = [c for c in enc_a.categories_[0]]  # str ids, encoder order
    coef_by_id = {aid: intercept + a_coefs[i] + mean_meet
                  for i, aid in enumerate(athlete_ids)}
    meta["adj_pace_sec_per_km"] = [
        coef_by_id.get(str(aid), np.nan) for aid in meta.index
    ]
    meta["meet_adjusted"] = True
    return meta.reset_index()


def _add_rating(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Add a 0-100 rating (z-scored within each group; higher = faster)."""
    def _score(g: pd.DataFrame) -> pd.DataFrame:
        mu = g["adj_pace_sec_per_km"].mean()
        sd = g["adj_pace_sec_per_km"].std(ddof=0) or 1.0
        # faster pace (lower) -> higher rating
        g = g.copy()
        g["rating"] = 50.0 + 10.0 * (mu - g["adj_pace_sec_per_km"]) / sd
        g["rank_in_group"] = g["adj_pace_sec_per_km"].rank(method="min").astype(int)
        return g

    return (
        df.groupby(group_cols, group_keys=False)[df.columns.tolist()]
        .apply(_score)
        .reset_index(drop=True)
    )


def compute_athlete_ratings(
    results: pd.DataFrame, alpha: float = 5.0
) -> pd.DataFrame:
    """Meet-adjusted athlete ratings per (gender, season)."""
    df = with_pace(results).dropna(subset=["pace_sec_per_km"])
    df = df[df["meet_name"].notna()]
    if df.empty:
        return pd.DataFrame(
            columns=["gender", "season", "athlete_id", "athlete_name", "team",
                     "conference", "races", "adj_pace_sec_per_km", "meet_adjusted",
                     "rating", "rank_in_group"]
        )
    parts = []
    for (gender, season), grp in df.groupby(["gender", "season"]):
        part = _fit_group(grp, alpha)
        part["gender"] = gender
        part["season"] = season
        parts.append(part)
    out = pd.concat(parts, ignore_index=True)
    out = _add_rating(out, ["gender", "season"])
    return out.sort_values(["gender", "season", "adj_pace_sec_per_km"]).reset_index(drop=True)


def compute_career_ratings(results: pd.DataFrame, alpha: float = 5.0) -> pd.DataFrame:
    """Career meet-adjusted ratings per gender (meets are season-unique)."""
    df = with_pace(results).dropna(subset=["pace_sec_per_km"])
    df = df[df["meet_name"].notna()]
    if df.empty:
        return pd.DataFrame()
    parts = []
    for gender, grp in df.groupby("gender"):
        part = _fit_group(grp, alpha)
        part["gender"] = gender
        parts.append(part)
    out = pd.concat(parts, ignore_index=True)
    out = _add_rating(out, ["gender"])
    return out.sort_values(["gender", "adj_pace_sec_per_km"]).reset_index(drop=True)


def top_runners(ratings: pd.DataFrame, gender: str, season: int | None = None,
                n: int = 25) -> pd.DataFrame:
    df = ratings[ratings["gender"] == gender]
    if season is not None and "season" in df.columns:
        df = df[df["season"] == season]
    return df.sort_values("rating", ascending=False).head(n).reset_index(drop=True)


def load_and_rate(engine=None) -> pd.DataFrame:
    """Convenience: load DB and compute seasonal athlete ratings."""
    frames = load_frames(engine)
    return compute_athlete_ratings(frames["results"])
