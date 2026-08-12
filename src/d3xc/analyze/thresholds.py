"""Tier thresholds: how fast must a team's top-5 be to win the OAC, win the NCAC,
make nationals, or win nationals — and how much improvement that implies vs a
typical freshman arrival.

Team level at a championship = mean of its 5 fastest actual finish times at that
meet (championship distance: men 8k / women 6k), so it's course-consistent within
a meet. National tiers use the full field (tracked + national-context teams).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from d3xc.analyze.development import champ_season_best


def _team_top5_at_meet(res, meet_name, season, gender, team):
    r = res[(res["meet_name"] == meet_name) & (res["season"] == season)
            & (res["gender"] == gender) & (res["team"] == team)].dropna(subset=["mark_seconds"])
    top = r.nsmallest(5, "mark_seconds")["mark_seconds"]
    return float(top.mean()) if len(top) >= 5 else np.nan


def tier_levels(frames: dict) -> pd.DataFrame:
    """One row per (tier, gender, season): the qualifying team + its top-5 time."""
    pl, res = frames["placements"], frames["results"]
    rows = []

    def _champs(mask, tier):
        d = pl[mask & (pl["team_place"] == 1)]
        for _, c in d.iterrows():
            v = _team_top5_at_meet(res, c["meet_name"], c["season"], c["gender"], c["team"])
            if v == v:
                rows.append({"tier": tier, "gender": c["gender"],
                             "season": int(c["season"]), "team": c["team"], "top5_s": v})

    conf = pl["meet_kind"] == "conference"
    _champs(conf & pl["meet_name"].str.contains("Ohio Athletic|OAC", case=False, na=False), "Win OAC")
    _champs(conf & pl["meet_name"].str.contains("Coast|NCAC", case=False, na=False), "Win NCAC")

    nat = pl[pl["meet_kind"] == "national"]
    for (season, gender, mn), g in nat.groupby(["season", "gender", "meet_name"]):
        vals = {t: _team_top5_at_meet(res, mn, season, gender, t)
                for t in g.dropna(subset=["team_place"])["team"].unique()}
        vals = {t: v for t, v in vals.items() if v == v}
        if not vals:
            continue
        best_t = min(vals, key=vals.get)
        last_t = max(vals, key=vals.get)
        rows.append({"tier": "Win Nationals", "gender": gender, "season": int(season),
                     "team": best_t, "top5_s": vals[best_t]})
        rows.append({"tier": "Make Nationals (last in)", "gender": gender,
                     "season": int(season), "team": last_t, "top5_s": vals[last_t]})
    return pd.DataFrame(rows)


def tier_summary(frames: dict) -> pd.DataFrame:
    """Per gender/tier: how fast the top-5 has needed to be (median & range)."""
    tl = tier_levels(frames)
    if tl.empty:
        return tl
    return (tl.groupby(["gender", "tier"])["top5_s"]
            .agg(years="count", median_s="median", best_s="min", worst_s="max")
            .reset_index())


def arrival_caliber(frames: dict) -> pd.DataFrame:
    """Typical freshman arrival: median of athletes' debut-season championship
    time (tracked teams), per gender — the baseline the tiers are measured from."""
    cb = champ_season_best(frames["results"]).sort_values(["athlete_id", "season"])
    debut = cb.groupby("athlete_id").head(1)
    return (debut.groupby("gender")["champ_best_s"]
            .agg(athletes="count", median_arrival_s="median").reset_index())


def tier_rolling(frames: dict, windows=(5, 3, 1)) -> pd.DataFrame:
    """Per tier/gender: mean top-5 bar over the trailing 5/3/1 seasons vs all-time,
    to expose recent shifts in how fast you must be. (Championship times are
    course-confounded across years, so treat as indicative of the trend.)"""
    tl = tier_levels(frames)
    if tl.empty:
        return tl
    last = int(tl["season"].max())
    rows = []
    for (tier, gender), g in tl.groupby(["tier", "gender"]):
        g = g.sort_values("season")
        rec = {"tier": tier, "gender": gender, "all_s": float(g["top5_s"].mean())}
        for w in windows:
            sub = g[g["season"] > last - w]
            rec[f"roll{w}_s"] = float(sub["top5_s"].mean()) if len(sub) else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)
