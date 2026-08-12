"""Athlete & program development — how runners improve year over year.

Because HS times are not automatically scrapeable (Athletic.net blocks bots),
the reliable, fully-data-driven backbone of the "pipeline" question is college
development:

  * athlete_progression   - each runner's season-best curve + year-over-year Δ
  * class_transition_stats - mean improvement by college-year transition
  * program_development_effect - which programs improve runners MORE than their
    arrival caliber predicts (controls for debut speed via regression; the
    program's mean residual = development over/under-performance)

The HS baseline, when curated (config/hs_marks.csv), plugs into
metrics.hs_to_college; here 'incoming caliber' is proxied by debut-season time.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from d3xc.analyze.metrics import athlete_season_best
from d3xc.scrape.timeutil import riegel_project

STD_M = {"men": 8000, "women": 6000}


def champ_season_best(results: pd.DataFrame, prefer_champ: bool = True,
                      exp: float = 1.06) -> pd.DataFrame:
    """Per athlete/season: best championship-distance-equivalent time (seconds).

    Uses a fatigue-adjusted (Riegel) conversion so a 5k isn't treated as 8k pace.
    If prefer_champ and the athlete has an actual championship-distance race that
    season (men 8k / women 6k), the best of THOSE is used and shorter races are
    ignored (once you're racing 8k, the converted 5k shouldn't set your mark).
    Otherwise the best Riegel-projected time across their races is used.
    """
    df = results.dropna(subset=["mark_seconds", "distance_m"]).copy()
    if "tracked" in df.columns:
        df = df[df["tracked"]]
    if df.empty:
        return pd.DataFrame(columns=["athlete_id", "athlete_name", "team",
                                     "gender", "season", "champ_best_s", "from_champ"])
    df["std_m"] = df["gender"].map(STD_M)
    df["equiv"] = [riegel_project(t, d, s, exp)
                   for t, d, s in zip(df["mark_seconds"], df["distance_m"], df["std_m"])]
    df["is_champ"] = df["distance_m"] == df["std_m"]
    # drop corrupt marks: a plausible std-distance (8k/6k) equivalent is
    # ~18:00-55:00 (1080-3300s). Anything outside is a parse error.
    df = df[(df["equiv"] >= 1080) & (df["equiv"] <= 3300)]
    if df.empty:
        return pd.DataFrame(columns=["athlete_id", "athlete_name", "team",
                                     "gender", "season", "champ_best_s", "from_champ"])
    rows = []
    for (aid, season), g in df.groupby(["athlete_id", "season"]):
        champ = g[g["is_champ"]]
        if prefer_champ and not champ.empty:
            best, src = champ["mark_seconds"].min(), True
        else:
            best, src = g["equiv"].min(), False
        r0 = g.iloc[0]
        rows.append((aid, r0["athlete_name"], r0["team"], r0["gender"],
                     int(season), float(best), src))
    return pd.DataFrame(rows, columns=["athlete_id", "athlete_name", "team",
                                       "gender", "season", "champ_best_s", "from_champ"])


def program_development_effect(results: pd.DataFrame, min_seasons: int = 2,
                               min_athletes: int = 5, method: str = "champ") -> pd.DataFrame:
    """Which programs develop runners beyond their arrival caliber?

    method='champ' (default) uses the fatigue-adjusted, championship-preferred
    season best (recommended); method='pace' uses the old linear-pace std time.

    improvement = debut season best - career best (seconds). We regress
    improvement on debut within each gender (slower arrivals have more room) and
    report each program's mean residual = development beyond arrival caliber.
    """
    if method == "champ":
        best = champ_season_best(results).rename(columns={"champ_best_s": "val"})
    else:
        b = athlete_season_best(results)
        best = b.rename(columns={"std_time_seconds": "val"})
    best = best.sort_values(["athlete_id", "season"])
    rows = []
    for aid, g in best.groupby("athlete_id"):
        if g["season"].nunique() < min_seasons:
            continue
        debut = g.iloc[0]["val"]
        peak = g["val"].min()
        rows.append((aid, g.iloc[0]["team"], g.iloc[0]["gender"], debut, debut - peak))
    df = pd.DataFrame(rows, columns=["athlete_id", "team", "gender", "debut", "improvement"])
    if df.empty:
        return df
    df["expected"] = np.nan
    for gender, gi in df.groupby("gender"):
        if len(gi) >= 5 and gi["debut"].nunique() > 1:
            b1, b0 = np.polyfit(gi["debut"], gi["improvement"], 1)
            df.loc[gi.index, "expected"] = b1 * gi["debut"] + b0
        else:
            df.loc[gi.index, "expected"] = gi["improvement"].mean()
    df["residual"] = df["improvement"] - df["expected"]
    eff = (df.groupby(["team", "gender"])
           .agg(athletes=("residual", "size"),
                mean_improve_s=("improvement", "mean"),
                dev_effect_s=("residual", "mean"))
           .reset_index())
    eff = eff[eff["athletes"] >= min_athletes]
    return eff.sort_values("dev_effect_s", ascending=False).reset_index(drop=True)


def athlete_progression(results: pd.DataFrame) -> pd.DataFrame:
    """Per athlete/season: standardized season-best + year-over-year delta and
    a 1-based college-year index (proxy for FR/SO/JR/SR)."""
    best = athlete_season_best(results).sort_values(["athlete_id", "season"])
    if best.empty:
        return best
    best["year_idx"] = best.groupby("athlete_id").cumcount() + 1
    best["prev"] = best.groupby("athlete_id")["std_time_seconds"].shift(1)
    best["yoy_improve_s"] = best["prev"] - best["std_time_seconds"]  # + = faster
    return best


def class_transition_stats(results: pd.DataFrame) -> pd.DataFrame:
    """Mean year-over-year improvement by college-year transition, per gender."""
    prog = athlete_progression(results)
    prog = prog.dropna(subset=["yoy_improve_s"])
    prog["transition"] = "yr" + (prog["year_idx"] - 1).astype(str) + "→yr" + prog["year_idx"].astype(str)
    return (prog.groupby(["gender", "transition"])
            .agg(n=("yoy_improve_s", "size"),
                 mean_improve_s=("yoy_improve_s", "mean"),
                 median_improve_s=("yoy_improve_s", "median"))
            .reset_index().sort_values(["gender", "transition"]))

