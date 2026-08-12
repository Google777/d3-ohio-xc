"""LacTiC v2 — chronological Elo ratings (predictive, not reactionary).

Every XC race is a set of head-to-head comparisons. We process races in date
order and update each runner's Elo from how they finished versus the field. A
runner's rating *before* a race is therefore a genuine prediction of that race,
which is what lets us validate predictive power out-of-sample (see validate.py).

Design:
  * multiplayer Elo: in a race of n runners, expected wins for i =
    sum_j 1/(1+10^((R_j-R_i)/400)); actual wins = (# runners beaten);
    R_i += K * (actual - expected) / (n-1).
  * cross-season carryover with partial regression to the mean (rosters churn,
    athletes improve) controlled by SEASON_REGRESSION.
  * new runners enter at BASE (per gender identical; scale is relative).

Team strength for a season = mean pre-championship Elo of a team's top 5.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from d3xc.analyze.metrics import load_frames
from d3xc.scrape.timeutil import parse_meet_date

BASE = 1500.0
K = 28.0
SEASON_REGRESSION = 0.25   # fraction pulled back toward BASE between seasons


def _race_order(results: pd.DataFrame) -> pd.DataFrame:
    """Attach a sortable race datetime + race key; drop rows without a time."""
    df = results.dropna(subset=["mark_seconds"]).copy()
    df["date_int"] = df["meet_date"].map(parse_meet_date)
    # fallback: season with mid-year so undated meets still sort within season
    df["date_int"] = df["date_int"].fillna(df["season"] * 10000 + 1015).astype(int)
    df["race_key"] = (df["season"].astype(str) + "|" + df["gender"] + "|"
                      + df["meet_name"].astype(str))
    return df


def compute_elo(results: pd.DataFrame, k: float = K,
                season_regression: float = SEASON_REGRESSION) -> pd.DataFrame:
    """Run chronological Elo. Returns a per-(athlete,race) history with the
    pre-race and post-race rating, finish place, and field size."""
    df = _race_order(results)
    if "tracked" in df.columns:
        df = df[df["tracked"]]
    if df.empty:
        return pd.DataFrame()

    # process gender independently (separate rating pools)
    history = []
    for gender, gdf in df.groupby("gender"):
        ratings: dict[int, float] = {}
        last_season: dict[int, int] = {}
        # order races chronologically
        races = (gdf.groupby(["date_int", "race_key", "season"])
                 .groups)
        for (date_int, race_key, season) in sorted(races.keys()):
            idx = races[(date_int, race_key, season)]
            race = gdf.loc[idx]
            # dense finish order by time (1 = fastest)
            place = race["mark_seconds"].rank(method="min").to_numpy()
            aids = race["athlete_id"].to_numpy()
            n = len(aids)
            if n < 2:
                continue
            # current ratings, with between-season regression to mean
            r = np.empty(n)
            for i, aid in enumerate(aids):
                cur = ratings.get(aid, BASE)
                if aid in last_season and season > last_season[aid]:
                    cur = BASE + (1 - season_regression) * (cur - BASE)
                r[i] = cur
            # expected vs actual wins
            diff = r[None, :] - r[:, None]              # R_j - R_i
            p = 1.0 / (1.0 + 10.0 ** (diff / 400.0))    # P(i beats j)
            np.fill_diagonal(p, 0.0)
            expected = p.sum(axis=1)
            actual = (n - place)                        # runners beaten
            new_r = r + k * (actual - expected) / (n - 1)
            for i, aid in enumerate(aids):
                history.append((aid, race["athlete_name"].iloc[i],
                                race["team"].iloc[i], gender, int(season),
                                int(date_int), race_key, float(r[i]),
                                float(new_r[i]), int(place[i]), n))
                ratings[aid] = new_r[i]
                last_season[aid] = season
    cols = ["athlete_id", "athlete_name", "team", "gender", "season",
            "date_int", "race_key", "pre_elo", "post_elo", "place", "field"]
    return pd.DataFrame(history, columns=cols)


def current_ratings(history: pd.DataFrame) -> pd.DataFrame:
    """Latest post-race Elo per athlete (their standing at end of data)."""
    if history.empty:
        return history
    last = history.sort_values("date_int").groupby("athlete_id").tail(1)
    return last[["athlete_id", "athlete_name", "team", "gender", "season",
                 "post_elo"]].rename(columns={"post_elo": "elo"}) \
        .sort_values("elo", ascending=False).reset_index(drop=True)


def team_elo_by_season(history: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """Team strength per season = mean of the team's top-N athletes' end-of-
    season Elo (their last post_elo that season)."""
    if history.empty:
        return history
    end = (history.sort_values("date_int")
           .groupby(["athlete_id", "season"]).tail(1))
    rows = []
    for (team, gender, season), g in end.groupby(["team", "gender", "season"]):
        top = g.nlargest(top_n, "post_elo")["post_elo"]
        if len(top) >= top_n:
            rows.append({"team": team, "gender": gender, "season": season,
                         "team_elo": float(top.mean()), "scorers": len(g)})
    return pd.DataFrame(rows).sort_values(["gender", "season", "team_elo"],
                                          ascending=[True, True, False]).reset_index(drop=True)


def load_and_run(engine=None) -> pd.DataFrame:
    return compute_elo(load_frames(engine)["results"])
