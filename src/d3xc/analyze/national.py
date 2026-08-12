"""National-championship context (NCAA DIII XC).

Uses the full national-meet field (tracked=False national teams + tracked=True
Ohio teams) purely at the championship, to answer: how do Ohio programs rank
against the national field, and who earns All-America?

D3 XC All-America = top 40 individuals at the national championship.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from d3xc.scrape.tfrrs import classify_meet_kind

ALL_AMERICAN_CUTOFF = 40


def national_team_standings(frames: dict, season: int, gender: str) -> pd.DataFrame:
    """Full national-meet team standings for a year, flagging Ohio programs."""
    pl = frames["placements"]
    d = pl[(pl["meet_kind"] == "national") & (pl["season"] == season)
           & (pl["gender"] == gender)].dropna(subset=["team_place"]).copy()
    if d.empty:
        return d
    d = d.sort_values("team_place")
    d["ohio"] = d["tracked"] if "tracked" in d.columns else False
    return d[["team_place", "team", "team_points", "ohio"]].reset_index(drop=True)


def ohio_at_nationals(frames: dict) -> pd.DataFrame:
    """Per season/gender: best Ohio team finish vs the national field size."""
    pl = frames["placements"]
    nat = pl[pl["meet_kind"] == "national"].dropna(subset=["team_place"])
    rows = []
    for (season, gender), g in nat.groupby(["season", "gender"]):
        field = int(g["team_place"].max())
        ohio = g[g["tracked"]] if "tracked" in g.columns else g.iloc[0:0]
        if ohio.empty:
            rows.append({"season": season, "gender": gender, "field_teams": field,
                         "ohio_qualifiers": 0, "best_ohio_team": None,
                         "best_ohio_place": None, "national_champion": _champ(g)})
            continue
        best = ohio.loc[ohio["team_place"].idxmin()]
        rows.append({
            "season": season, "gender": gender, "field_teams": field,
            "ohio_qualifiers": int(ohio["team"].nunique()),
            "best_ohio_team": best["team"], "best_ohio_place": int(best["team_place"]),
            "national_champion": _champ(g),
        })
    return pd.DataFrame(rows).sort_values(["gender", "season"]).reset_index(drop=True)


def _champ(g: pd.DataFrame):
    w = g[g["team_place"] == 1]["team"]
    return w.iloc[0] if len(w) else None


def all_americans(frames: dict, cutoff: int = ALL_AMERICAN_CUTOFF,
                  ohio_only: bool = True) -> pd.DataFrame:
    """Individuals finishing in the top `cutoff` at the national meet (All-America).
    ohio_only restricts to tracked (Ohio) programs."""
    r = frames["results"]
    if r.empty or "place_overall" not in r.columns:
        return pd.DataFrame()
    is_nat = r["meet_name"].map(lambda m: classify_meet_kind(m) == "national")
    nat = r[is_nat & r["place_overall"].notna()
            & (r["place_overall"] <= cutoff)].copy()
    if nat.empty:
        return nat
    if ohio_only and "tracked" in nat.columns:
        nat = nat[nat["tracked"]]
    return (nat[["season", "gender", "place_overall", "athlete_name", "team"]]
            .sort_values(["gender", "season", "place_overall"]).reset_index(drop=True))


def ohio_all_american_counts(frames: dict, cutoff: int = ALL_AMERICAN_CUTOFF) -> pd.DataFrame:
    """Count of Ohio All-Americans per program/gender over the decade."""
    aa = all_americans(frames, cutoff, ohio_only=True)
    if aa.empty:
        return aa
    return (aa.groupby(["team", "gender"]).size().reset_index(name="all_americans")
            .sort_values("all_americans", ascending=False).reset_index(drop=True))
