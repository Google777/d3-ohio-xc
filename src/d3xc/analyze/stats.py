"""Program-development statistics on the validated meet data.

All inputs are concrete (championship placements + real times), so every figure
here is directly traceable to a TFRRS result, not a model estimate.

Functions:
  * conference_champions  - champion (and runner-up) per conference/year
  * title_counts          - conference titles per program over the window
  * program_trajectories  - OLS trend of regional place & top-5 time per program
  * national_appearances  - NCAA championship appearances per program
  * athlete_development    - within-athlete season-best improvement stats
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps

from d3xc.analyze.metrics import (
    athlete_season_best,
    team_scoring_by_season,
    with_pace,
)

CONF_MEET = {"OAC": "Ohio Athletic|OAC", "NCAC": "Coast|NCAC",
             "HCAC": "HCAC|Heartland", "UAA": "UAA|University Athletic"}


def _ols_slope(x, y):
    """Return (slope, r2, p_value, n) via least squares; NaN if <3 points."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 3 or np.ptp(x) == 0:
        return (np.nan, np.nan, np.nan, len(x))
    lr = sps.linregress(x, y)
    return (float(lr.slope), float(lr.rvalue ** 2), float(lr.pvalue), int(len(x)))


# --------------------------------------------------------------------------
def conference_champions(placements: pd.DataFrame, conf: str) -> pd.DataFrame:
    """Champion + runner-up per season for a conference, both genders."""
    pat = CONF_MEET[conf]
    d = placements[(placements["meet_kind"] == "conference")
                   & (placements["meet_name"].str.contains(pat, case=False, na=False))]
    rows = []
    for (season, gender), g in d.groupby(["season", "gender"]):
        g = g.sort_values("team_place")
        champ = g[g["team_place"] == 1]["team"]
        second = g[g["team_place"] == 2]["team"]
        rows.append({
            "conference": conf, "season": season, "gender": gender,
            "champion": champ.iloc[0] if len(champ) else None,
            "runner_up": second.iloc[0] if len(second) else None,
            "teams": int(g["team"].nunique()),
        })
    return pd.DataFrame(rows).sort_values(["gender", "season"]).reset_index(drop=True)


def title_counts(placements: pd.DataFrame) -> pd.DataFrame:
    """Conference titles (team_place==1 at a conference meet) per team/gender."""
    d = placements[(placements["meet_kind"] == "conference")
                   & (placements["team_place"] == 1)]
    if d.empty:
        return pd.DataFrame(columns=["team", "gender", "titles"])
    return (d.groupby(["team", "gender"]).size().reset_index(name="titles")
            .sort_values("titles", ascending=False).reset_index(drop=True))


def program_trajectories(frames: dict) -> pd.DataFrame:
    """Per team/gender: OLS trend of regional placement and top-5 std time.

    reg_slope < 0  => finishing higher (improving).
    time_slope < 0 => getting faster (improving).
    """
    placements = frames["placements"]
    scoring = team_scoring_by_season(frames["results"])
    reg = placements[placements["meet_kind"] == "regional"]

    rows = []
    keys = scoring[["team", "conference", "gender"]].drop_duplicates()
    for _, k in keys.iterrows():
        team, conf, gender = k["team"], k["conference"], k["gender"]
        s = scoring[(scoring["team"] == team) & (scoring["gender"] == gender)].dropna(subset=["top5_avg"])
        t_slope, t_r2, t_p, t_n = _ols_slope(s["season"], s["top5_avg"])
        r = reg[(reg["team"] == team) & (reg["gender"] == gender)].dropna(subset=["team_place"])
        r_slope, r_r2, r_p, r_n = _ols_slope(r["season"], r["team_place"])
        rows.append({
            "team": team, "conference": conf, "gender": gender,
            "seasons": int(s["season"].nunique()),
            "time_slope_s_per_yr": t_slope, "time_r2": t_r2, "time_p": t_p,
            "reg_slope_place_per_yr": r_slope, "reg_r2": r_r2, "reg_p": r_p,
            "reg_n": r_n,
        })
    return pd.DataFrame(rows)


def national_appearances(placements: pd.DataFrame) -> pd.DataFrame:
    d = placements[placements["meet_kind"] == "national"]
    if d.empty:
        return pd.DataFrame(columns=["team", "gender", "appearances", "best_finish"])
    return (d.groupby(["team", "gender"])
            .agg(appearances=("season", "nunique"), best_finish=("team_place", "min"))
            .reset_index().sort_values(["appearances", "best_finish"],
                                       ascending=[False, True]).reset_index(drop=True))


def athlete_development(frames: dict, min_seasons: int = 2) -> pd.DataFrame:
    """Within-athlete improvement: debut season-best -> career-best std time."""
    best = athlete_season_best(frames["results"])
    rows = []
    for aid, g in best.groupby("athlete_id"):
        if g["season"].nunique() < min_seasons:
            continue
        g = g.sort_values("season")
        debut = g.iloc[0]["std_time_seconds"]
        career = g["std_time_seconds"].min()
        rows.append({
            "athlete_id": aid, "athlete_name": g.iloc[0]["athlete_name"],
            "team": g.iloc[0]["team"], "gender": g.iloc[0]["gender"],
            "seasons": int(g["season"].nunique()),
            "debut_time": debut, "career_best": career,
            "improvement_s": debut - career,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# competitive balance
# --------------------------------------------------------------------------
def competitive_balance(frames: dict) -> pd.DataFrame:
    """Per conference/gender/season: spread of team strength among that
    conference's Ohio teams (SD & CV of top-5 scoring time). Lower spread =
    more balanced. Also # of tracked teams scored."""
    scoring = team_scoring_by_season(frames["results"]).dropna(subset=["top5_avg"])
    rows = []
    for (conf, gender, season), g in scoring.groupby(["conference", "gender", "season"]):
        if len(g) < 3:
            continue
        t = g["top5_avg"]
        rows.append({
            "conference": conf, "gender": gender, "season": season,
            "n_teams": len(g),
            "sd_top5_s": float(t.std(ddof=0)),
            "cv_pct": float(100 * t.std(ddof=0) / t.mean()),
            "range_s": float(t.max() - t.min()),
        })
    return pd.DataFrame(rows).sort_values(["conference", "gender", "season"]).reset_index(drop=True)


def balance_trend(frames: dict) -> pd.DataFrame:
    """OLS trend of within-conference SD over seasons (negative = converging)."""
    cb = competitive_balance(frames)
    rows = []
    for (conf, gender), g in cb.groupby(["conference", "gender"]):
        slope, r2, p, n = _ols_slope(g["season"], g["sd_top5_s"])
        rows.append({"conference": conf, "gender": gender, "seasons": n,
                     "sd_slope_s_per_yr": slope, "r2": r2, "p": p})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# JCU -> NCAC realignment ripple (John Carroll left OAC for NCAC in 2025)
# --------------------------------------------------------------------------
def jcu_ncac_ripple(frames: dict) -> dict:
    """Quantify the 2025 realignment: JCU's own finishes, the NCAC Ohio teams it
    displaced, and the OAC title race it vacated."""
    pl = frames["placements"]
    conf = pl[pl["meet_kind"] == "conference"].copy()

    jcu = conf[conf["team"] == "John Carroll"][["season", "gender", "team_place", "meet_name"]]

    def _mean_place(team_pat, gender, seasons):
        d = conf[(conf["meet_name"].str.contains(team_pat, case=False, na=False))
                 & (conf["gender"] == gender) & (conf["season"].isin(seasons))]
        return d.groupby("team")["team_place"].mean()

    # NCAC Ohio teams: mean placement pre-JCU (2021-2024) vs 2025
    ncac_pre = _mean_place("Coast|NCAC", "men", [2021, 2022, 2023, 2024])
    ncac_2025 = _mean_place("Coast|NCAC", "men", [2025])
    ncac_shift = pd.DataFrame({"pre_2021_24": ncac_pre, "y2025": ncac_2025})
    ncac_shift["delta_places"] = ncac_shift["y2025"] - ncac_shift["pre_2021_24"]

    # OAC men champions around the transition
    oac = conf[(conf["meet_name"].str.contains("Ohio Athletic|OAC", case=False, na=False))
               & (conf["gender"] == "men") & (conf["team_place"] == 1)]
    oac_champs = oac.groupby("season")["team"].first().to_dict()

    return {
        "jcu_conference_finishes": jcu.sort_values(["gender", "season"]).to_dict("records"),
        "ncac_men_shift_2025_vs_2021_24": ncac_shift.round(2).reset_index().rename(
            columns={"index": "team"}).to_dict("records"),
        "oac_men_champions": oac_champs,
    }


# --------------------------------------------------------------------------
# rolling (multi-season) trajectory — smooths year-to-year swings, aligns with
# the ~4-year college cycle
# --------------------------------------------------------------------------
def _program_season_metrics(frames: dict) -> pd.DataFrame:
    """Per team/gender/season: top-5 scoring time and regional placement."""
    scoring = team_scoring_by_season(frames["results"])[
        ["team", "conference", "gender", "season", "top5_avg"]]
    reg = frames["placements"]
    reg = reg[reg["meet_kind"] == "regional"][["team", "gender", "season", "team_place"]]
    reg = reg.rename(columns={"team_place": "regional_place"})
    m = scoring.merge(reg, on=["team", "gender", "season"], how="left")
    return m.sort_values(["team", "gender", "season"]).reset_index(drop=True)


def rolling_program_metrics(frames: dict, window: int = 3) -> pd.DataFrame:
    """Add trailing rolling means (over the last `window` *competed* seasons, so
    the 2020 gap doesn't distort it) of top-5 time and regional place."""
    m = _program_season_metrics(frames)
    if m.empty:
        return m
    g = m.groupby(["team", "gender"], group_keys=False)
    m["roll_top5"] = g["top5_avg"].transform(
        lambda s: s.rolling(window, min_periods=1).mean())
    m["roll_regional"] = g["regional_place"].transform(
        lambda s: s.rolling(window, min_periods=1).mean())
    return m


def rolling_change(frames: dict, window: int = 3, min_seasons: int = 4) -> pd.DataFrame:
    """Per team/gender: net change in the rolling average (early→late) plus raw
    year-to-year volatility. Negative change = improving (faster / higher place).
    """
    m = rolling_program_metrics(frames, window)
    rows = []
    for (team, conf, gender), s in m.groupby(["team", "conference", "gender"]):
        s = s.dropna(subset=["top5_avg"])
        if s["season"].nunique() < min_seasons:
            continue
        rt = s["roll_top5"].dropna()
        rr = s["roll_regional"].dropna()
        # volatility = SD of raw season-to-season changes (the 'wild swings')
        vol_time = s["top5_avg"].diff().abs().mean()
        vol_reg = s["regional_place"].diff().abs().mean()
        rows.append({
            "team": team, "conference": conf, "gender": gender,
            "seasons": int(s["season"].nunique()),
            "roll_time_change_s": float(rt.iloc[-1] - rt.iloc[0]) if len(rt) else np.nan,
            "roll_regional_change": float(rr.iloc[-1] - rr.iloc[0]) if len(rr) else np.nan,
            "mean_yoy_swing_s": float(vol_time) if vol_time == vol_time else np.nan,
            "mean_yoy_swing_places": float(vol_reg) if vol_reg == vol_reg else np.nan,
        })
    out = pd.DataFrame(rows)
    return out.sort_values("roll_time_change_s").reset_index(drop=True) if not out.empty else out


# --------------------------------------------------------------------------
# recruiting reach (athlete origin: in-state vs national)
# --------------------------------------------------------------------------
def recruiting_reach(frames: dict) -> pd.DataFrame:
    """Per team/gender: how national is the roster? % of athletes (with known
    origin) from Ohio vs out-of-state, and how many distinct states."""
    a = frames.get("athletes")
    if a is None or a.empty or "home_state" not in a.columns:
        return pd.DataFrame()
    a = a[a["home_state"].notna()]
    if a.empty:
        return pd.DataFrame()
    rows = []
    for (team, gender), g in a.groupby(["team", "gender"]):
        n = len(g)
        in_state = int((g["home_state"] == "OH").sum())
        rows.append({
            "team": team, "gender": gender, "athletes_with_origin": n,
            "pct_in_state": round(100 * in_state / n, 1),
            "pct_out_of_state": round(100 * (n - in_state) / n, 1),
            "n_states": int(g["home_state"].nunique()),
        })
    return pd.DataFrame(rows).sort_values("pct_out_of_state", ascending=False).reset_index(drop=True)


def development_by_origin(frames: dict, min_seasons: int = 2) -> pd.DataFrame:
    """Do in-state vs out-of-state recruits arrive/develop differently?
    Joins each multi-season athlete's debut & improvement to their origin."""
    a = frames.get("athletes")
    if a is None or a.empty or "home_state" not in a.columns:
        return pd.DataFrame()
    best = athlete_season_best(frames["results"]).sort_values(["athlete_id", "season"])
    rows = []
    for aid, gp in best.groupby("athlete_id"):
        if gp["season"].nunique() < min_seasons:
            continue
        rows.append((aid, gp.iloc[0]["std_time_seconds"],
                     gp.iloc[0]["std_time_seconds"] - gp["std_time_seconds"].min()))
    imp = pd.DataFrame(rows, columns=["id", "debut", "improvement"])
    m = imp.merge(a[["id", "gender", "home_state"]], on="id", how="inner")
    m = m[m["home_state"].notna()]
    if m.empty:
        return m
    m["origin"] = np.where(m["home_state"] == "OH", "in-state (OH)", "out-of-state")
    return (m.groupby(["gender", "origin"])
            .agg(athletes=("id", "size"),
                 mean_debut_s=("debut", "mean"),
                 mean_improve_s=("improvement", "mean"))
            .reset_index().round(1))
