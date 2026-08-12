"""LacTiC PacePower — recency-weighted pace, the most predictive individual model.

Out-of-sample validation (temporal holdout) selected recency-weighted pace as
the strongest predictor of race finish order (~87% pairwise accuracy vs 84% for
career-best pace and 80% for head-to-head Elo). This module exposes it as a
forward-looking rating: each athlete's EWMA pace is their *predicted* next-race
pace, projected to the gender's championship distance as a predicted time.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from d3xc.analyze.metrics import STD_KM, load_frames, with_pace
from d3xc.scrape.timeutil import parse_meet_date, seconds_to_time

EWMA_SPAN = 3


def pace_power(results: pd.DataFrame, span: int = EWMA_SPAN) -> pd.DataFrame:
    """Per athlete: current recency-weighted predicted pace + projected time.

    Uses each athlete's most recent EWMA(span) of pace over their race history.
    Returns one row per athlete with a 0-100 rating within gender/season pool.
    """
    df = with_pace(results).dropna(subset=["pace_sec_per_km"]).copy()
    if "tracked" in df.columns:
        df = df[df["tracked"]]
    if df.empty:
        return pd.DataFrame()
    df["date_int"] = df["meet_date"].map(parse_meet_date)
    df["date_int"] = df["date_int"].fillna(df["season"] * 10000 + 1015).astype(int)
    df = df.sort_values(["athlete_id", "date_int"])
    df["ewma"] = df.groupby("athlete_id")["pace_sec_per_km"].transform(
        lambda s: s.ewm(span=span).mean())

    # latest EWMA per athlete = current predicted pace
    last = df.groupby("athlete_id").tail(1).copy()
    last = last.rename(columns={"ewma": "pred_pace_sec_per_km"})
    last["races"] = df.groupby("athlete_id")["pace_sec_per_km"].count().values \
        if False else last["athlete_id"].map(df.groupby("athlete_id").size())
    last["std_km"] = last["gender"].map(STD_KM)
    last["proj_time_sec"] = last["pred_pace_sec_per_km"] * last["std_km"]
    last["proj_time"] = last["proj_time_sec"].map(seconds_to_time)

    # 0-100 rating within gender (higher = faster)
    def _rate(g):
        mu, sd = g["pred_pace_sec_per_km"].mean(), g["pred_pace_sec_per_km"].std(ddof=0) or 1.0
        g = g.copy()
        g["rating"] = 50 + 10 * (mu - g["pred_pace_sec_per_km"]) / sd
        return g
    out = last.groupby("gender", group_keys=False)[last.columns.tolist()].apply(_rate)
    cols = ["athlete_id", "athlete_name", "team", "gender", "season", "races",
            "pred_pace_sec_per_km", "proj_time_sec", "proj_time", "rating"]
    return out[cols].sort_values(["gender", "pred_pace_sec_per_km"]).reset_index(drop=True)


def team_pace_power(results: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """Team predicted strength = mean projected time of its top-N athletes."""
    pp = pace_power(results)
    if pp.empty:
        return pp
    rows = []
    for (team, gender), g in pp.groupby(["team", "gender"]):
        top = g.nsmallest(top_n, "proj_time_sec")
        if len(top) >= top_n:
            rows.append({"team": team, "gender": gender,
                         "team_proj_time_sec": float(top["proj_time_sec"].mean()),
                         "team_proj_time": seconds_to_time(top["proj_time_sec"].mean())})
    return pd.DataFrame(rows).sort_values(["gender", "team_proj_time_sec"]).reset_index(drop=True)


def top_predicted(results: pd.DataFrame, gender: str, n: int = 20) -> pd.DataFrame:
    pp = pace_power(results)
    return pp[pp["gender"] == gender].head(n).reset_index(drop=True)


def load_and_run(engine=None) -> pd.DataFrame:
    return pace_power(load_frames(engine)["results"])


def rolling_team_projection(results: pd.DataFrame, window: int = 3,
                            top_n: int = 5) -> pd.DataFrame:
    """Smoothed team strength: each athlete's std-distance form is a trailing
    rolling mean over their last `window` seasons (dampens one-off great/off
    races); team = mean of its top-5 smoothed athletes. More stable than a
    single-season projection and aligned with the college cycle.
    """
    from d3xc.analyze.metrics import athlete_season_best
    best = athlete_season_best(results).sort_values(["athlete_id", "season"])
    if best.empty:
        return pd.DataFrame()
    best["roll"] = best.groupby("athlete_id")["std_time_seconds"].transform(
        lambda s: s.rolling(window, min_periods=1).mean())
    latest = best.groupby("athlete_id").tail(1)   # each athlete's current form
    rows = []
    for (team, gender), g in latest.groupby(["team", "gender"]):
        top = g.nsmallest(top_n, "roll")
        if len(top) >= top_n:
            rows.append({"team": team, "gender": gender,
                         "team_roll_time_sec": float(top["roll"].mean()),
                         "team_roll_time": seconds_to_time(top["roll"].mean())})
    return pd.DataFrame(rows).sort_values(["gender", "team_roll_time_sec"]).reset_index(drop=True)
