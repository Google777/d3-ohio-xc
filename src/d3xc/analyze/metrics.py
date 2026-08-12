"""Development metrics.

All race marks are normalized to *pace* (seconds per km) so results run at
different distances (early-season 5k vs championship 8k/6k) are comparable, then
projected back to each gender's standard championship distance for display.

Metric families:
  * team season scoring: top-5 / top-7 average, 1-5 pack spread
  * athlete development: season-best progression, most-improved leaderboard
  * team development: conference placement/wins, regional & national placement
  * HS -> college: pace delta from linked high-school marks (confidence-gated)
  * coaching overlays: tenure spans for timeline annotation
"""
from __future__ import annotations

import pandas as pd

from d3xc import config
from d3xc.store.db import (
    Athlete,
    CoachTenure,
    HSMarkRow,
    Result,
    Team,
    TeamPlacement,
    get_engine,
)

STD_KM = {"men": 8.0, "women": 6.0}
MEET_ORDER = {"invitational": 0, "conference": 1, "regional": 2, "national": 3}


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------
def load_frames(engine=None) -> dict[str, pd.DataFrame]:
    """Read all tables into DataFrames joined with human-readable team names."""
    engine = engine or get_engine()
    with engine.connect() as conn:
        teams = pd.read_sql_table(Team.__tablename__, conn)
        athletes = pd.read_sql_table(Athlete.__tablename__, conn)
        results = pd.read_sql_table(Result.__tablename__, conn)
        placements = pd.read_sql_table(TeamPlacement.__tablename__, conn)
        coaches = pd.read_sql_table(CoachTenure.__tablename__, conn)
        hs = pd.read_sql_table(HSMarkRow.__tablename__, conn)

    team_names = teams.set_index("id")["name"]
    team_conf = teams.set_index("id")["conference"]
    team_tracked = (teams.set_index("id")["tracked"] if "tracked" in teams.columns
                    else None)
    # Always attach human-readable columns (read_sql returns schema columns even
    # for empty tables, so .map works and downstream filters never KeyError).
    for df in (results, placements, coaches):
        df["team"] = df["team_id"].map(team_names)
        df["conference"] = df["team_id"].map(team_conf)
        if team_tracked is not None:
            df["tracked"] = df["team_id"].map(team_tracked).fillna(True).astype(bool)
    athletes["team"] = athletes["team_id"].map(team_names)
    athletes["conference"] = athletes["team_id"].map(team_conf)
    if team_tracked is not None:
        athletes["tracked"] = athletes["team_id"].map(team_tracked).fillna(True).astype(bool)
    results = results.merge(
        athletes[["id", "name"]].rename(
            columns={"id": "athlete_id", "name": "athlete_name"}),
        on="athlete_id",
        how="left",
    )
    hs["college_team"] = hs["college_team_id"].map(team_names)
    return {
        "teams": teams,
        "athletes": athletes,
        "results": results,
        "placements": placements,
        "coaches": coaches,
        "hs": hs,
    }


# --------------------------------------------------------------------------
# pace normalization
# --------------------------------------------------------------------------
def with_pace(results: pd.DataFrame) -> pd.DataFrame:
    """Add pace_sec_per_km and std_time_seconds (projected to standard distance)."""
    df = results.copy()
    if df.empty:
        df["pace_sec_per_km"] = []
        df["std_time_seconds"] = []
        return df
    dist_km = df["distance_m"].fillna(0) / 1000.0
    df["pace_sec_per_km"] = df["mark_seconds"] / dist_km.where(dist_km > 0)
    df["std_km"] = df["gender"].map(STD_KM)
    df["std_time_seconds"] = df["pace_sec_per_km"] * df["std_km"]
    return df


def athlete_season_best(results: pd.DataFrame) -> pd.DataFrame:
    """Best (fastest) standardized time per athlete per season (tracked teams)."""
    if "tracked" in results.columns:
        results = results[results["tracked"]]
    df = with_pace(results)
    df = df.dropna(subset=["std_time_seconds"])
    if df.empty:
        return pd.DataFrame(
            columns=["athlete_id", "athlete_name", "team", "conference",
                     "gender", "season", "std_time_seconds", "pace_sec_per_km"]
        )
    idx = df.groupby(["athlete_id", "season"])["std_time_seconds"].idxmin()
    return df.loc[idx, [
        "athlete_id", "athlete_name", "team", "conference", "gender",
        "season", "std_time_seconds", "pace_sec_per_km",
    ]].reset_index(drop=True)


# --------------------------------------------------------------------------
# team season scoring
# --------------------------------------------------------------------------
def team_scoring_by_season(results: pd.DataFrame) -> pd.DataFrame:
    """Top-5/top-7 scoring average and 1-5 pack spread per team/gender/season."""
    best = athlete_season_best(results)
    rows = []
    for (team, conf, gender, season), grp in best.groupby(
        ["team", "conference", "gender", "season"]
    ):
        times = grp["std_time_seconds"].sort_values().tolist()
        rows.append({
            "team": team,
            "conference": conf,
            "gender": gender,
            "season": season,
            "n_athletes": len(times),
            "top5_avg": _avg(times[:5]) if len(times) >= 5 else None,
            "top7_avg": _avg(times[:7]) if len(times) >= 7 else None,
            "spread_1_5": (times[4] - times[0]) if len(times) >= 5 else None,
        })
    return pd.DataFrame(rows).sort_values(["team", "gender", "season"]).reset_index(drop=True)


def _avg(xs):
    return sum(xs) / len(xs) if xs else None


# --------------------------------------------------------------------------
# athlete development / most improved
# --------------------------------------------------------------------------
def most_improved_athletes(results: pd.DataFrame, min_seasons: int = 2) -> pd.DataFrame:
    """Improvement from debut-season best to career-best standardized time.

    Positive `improvement_seconds` means the athlete got faster.
    """
    best = athlete_season_best(results)
    rows = []
    for aid, grp in best.groupby("athlete_id"):
        if grp["season"].nunique() < min_seasons:
            continue
        grp = grp.sort_values("season")
        debut = grp.iloc[0]
        peak_time = grp["std_time_seconds"].min()
        improvement = debut["std_time_seconds"] - peak_time
        rows.append({
            "athlete_id": aid,
            "athlete_name": debut["athlete_name"],
            "team": debut["team"],
            "conference": debut["conference"],
            "gender": debut["gender"],
            "debut_season": int(debut["season"]),
            "seasons": int(grp["season"].nunique()),
            "debut_time": debut["std_time_seconds"],
            "best_time": peak_time,
            "improvement_seconds": improvement,
            "improvement_pct": 100.0 * improvement / debut["std_time_seconds"],
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("improvement_seconds", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# team development from placements
# --------------------------------------------------------------------------
def placement_trend(placements: pd.DataFrame, meet_kind: str) -> pd.DataFrame:
    """Team placement over seasons for a given meet kind (lower place = better)."""
    df = placements[placements["meet_kind"] == meet_kind].copy()
    cols = ["team", "conference", "gender", "season", "team_place", "team_points"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    return df[cols].sort_values(["team", "gender", "season"]).reset_index(drop=True)


def conference_wins(placements: pd.DataFrame) -> pd.DataFrame:
    """Count of conference-meet wins (team_place == 1) per team/gender."""
    df = placements[
        (placements["meet_kind"] == "conference") & (placements["team_place"] == 1)
    ]
    if df.empty:
        return pd.DataFrame(columns=["team", "gender", "conference_titles"])
    return (
        df.groupby(["team", "gender"]).size().reset_index(name="conference_titles")
        .sort_values("conference_titles", ascending=False).reset_index(drop=True)
    )


def most_improved_teams(placements: pd.DataFrame, meet_kind: str = "regional") -> pd.DataFrame:
    """Improvement in placement from first to last season (positive = moved up)."""
    trend = placement_trend(placements, meet_kind)
    rows = []
    for (team, gender), grp in trend.groupby(["team", "gender"]):
        grp = grp.dropna(subset=["team_place"]).sort_values("season")
        if grp["season"].nunique() < 2:
            continue
        first, last = grp.iloc[0], grp.iloc[-1]
        rows.append({
            "team": team,
            "gender": gender,
            "conference": first["conference"],
            "first_season": int(first["season"]),
            "last_season": int(last["season"]),
            "first_place": int(first["team_place"]),
            "last_place": int(last["team_place"]),
            "places_gained": int(first["team_place"] - last["team_place"]),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("places_gained", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# HS -> college
# --------------------------------------------------------------------------
def hs_to_college(results: pd.DataFrame, hs: pd.DataFrame,
                  min_confidence: float = 0.6) -> pd.DataFrame:
    """Pace delta between linked HS mark and college career-best (confidence-gated)."""
    if hs.empty:
        return pd.DataFrame()
    hs = hs[hs["match_confidence"] >= min_confidence].copy()
    if hs.empty:
        return pd.DataFrame()
    hs["hs_event_km"] = hs["event"].map(_event_to_km)
    hs["hs_pace"] = hs["mark_seconds"] / hs["hs_event_km"]

    best = athlete_season_best(results)
    college_best = (
        best.groupby(["athlete_name", "team", "gender"])["pace_sec_per_km"].min()
        .reset_index().rename(columns={"pace_sec_per_km": "college_best_pace"})
    )
    merged = hs.merge(
        college_best,
        left_on=["athlete_name", "college_team", "gender"],
        right_on=["athlete_name", "team", "gender"],
        how="inner",
    )
    if merged.empty:
        return merged
    merged["pace_delta"] = merged["hs_pace"] - merged["college_best_pace"]
    merged["pace_improvement_pct"] = 100.0 * merged["pace_delta"] / merged["hs_pace"]
    return merged.sort_values("pace_improvement_pct", ascending=False).reset_index(drop=True)


def _event_to_km(event: str) -> float:
    e = str(event).lower().replace(" ", "")
    table = {
        "1600m": 1.6, "1600": 1.6, "mile": 1.609,
        "3200m": 3.2, "3200": 3.2, "2mile": 3.219,
        "5000m": 5.0, "5000": 5.0, "5k": 5.0, "5km": 5.0,
        "6000m": 6.0, "6k": 6.0,
        "8000m": 8.0, "8k": 8.0,
    }
    return table.get(e, 5.0)


# --------------------------------------------------------------------------
# coaching overlays
# --------------------------------------------------------------------------
def coaching_overlays(coaches: pd.DataFrame, team: str, gender: str) -> pd.DataFrame:
    """Coach tenures for a team, expanded to concrete end years for plotting."""
    if coaches.empty:
        return coaches
    df = coaches[
        (coaches["team"] == team)
        & (coaches["gender"].isin([gender, "both"]))
    ].copy()
    if df.empty:
        return df
    df["end_year"] = df["end_year"].fillna(config.LAST_SEASON)
    return df.sort_values("start_year").reset_index(drop=True)


# --------------------------------------------------------------------------
# comprehensive per-school / per-season timeline
# --------------------------------------------------------------------------
def coach_for(coaches: pd.DataFrame, team: str, gender: str, season: int):
    """Return the head coach for a team/gender/season, or None if unknown.

    coaches.csv uses gender codes m|f|both; map them to men|women here.
    """
    if coaches is None or coaches.empty:
        return None
    gmap = {"m": "men", "f": "women", "men": "men", "women": "women", "both": "both"}
    df = coaches[coaches["team"] == team]
    for _, r in df.iterrows():
        cg = gmap.get(str(r["gender"]).strip().lower(), str(r["gender"]))
        if cg not in (gender, "both"):
            continue
        start = r["start_year"]
        end = r["end_year"] if pd.notna(r["end_year"]) else config.LAST_SEASON
        if start <= season <= end:
            return r["coach_name"]
    return None


def school_timeline(frames: dict) -> pd.DataFrame:
    """One row per (team, gender, season) with championship finishes, top-5
    scoring time, pack spread, roster depth, and the coach of record.

    Built from concrete meet data (placements + individual results), not the
    ML ratings, so values are directly verifiable.
    """
    results = frames["results"]
    placements = frames["placements"]
    coaches = frames["coaches"]
    scoring = team_scoring_by_season(results)

    def _place(kind: str) -> pd.Series:
        d = placements[placements["meet_kind"] == kind]
        if d.empty:
            return pd.Series(dtype="float64")
        return d.groupby(["team", "gender", "season"])["team_place"].min()

    conf, reg, nat = _place("conference"), _place("regional"), _place("national")

    rows = []
    for _, r in scoring.iterrows():
        key = (r["team"], r["gender"], r["season"])
        rows.append({
            "team": r["team"],
            "conference": r["conference"],
            "gender": r["gender"],
            "season": int(r["season"]),
            "coach": coach_for(coaches, r["team"], r["gender"], r["season"]),
            "conf_place": _get(conf, key),
            "regional_place": _get(reg, key),
            "national_place": _get(nat, key),
            "top5_avg_seconds": r["top5_avg"],
            "spread_1_5": r["spread_1_5"],
            "n_athletes": int(r["n_athletes"]),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["team", "gender", "season"]).reset_index(drop=True)


def _get(series: pd.Series, key):
    try:
        v = series.get(key)
        return int(v) if v is not None and pd.notna(v) else None
    except (KeyError, TypeError):
        return None
