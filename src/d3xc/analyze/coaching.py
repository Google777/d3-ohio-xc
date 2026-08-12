"""Program dynamics: multi-window acceleration, and coaching-change effects on
performance, recruiting caliber, and recruiting reach.

All descriptive/correlational. Coaching changes are matched from
config/coaches.csv; recent (2024) changes have thin 'after' windows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from d3xc.analyze.development import champ_season_best

STD_GENDER = {"men", "women"}


def program_strength_series(frames: dict) -> pd.DataFrame:
    """team/gender/season -> top-5 championship time (s) + regional place."""
    cb = champ_season_best(frames["results"])
    rows = []
    for (team, gender, season), g in cb.groupby(["team", "gender", "season"]):
        vals = g["champ_best_s"].nsmallest(5)
        if len(vals) >= 5:
            rows.append((team, gender, int(season), float(vals.mean())))
    s = pd.DataFrame(rows, columns=["team", "gender", "season", "top5_s"])
    pl = frames["placements"]
    reg = (pl[pl["meet_kind"] == "regional"][["team", "gender", "season", "team_place"]]
           .rename(columns={"team_place": "regional"}))
    return s.merge(reg, on=["team", "gender", "season"], how="left")


def _rate(series_df: pd.DataFrame, col: str, last: int, window: int):
    """OLS slope of `col` vs season over the trailing `window` calendar years
    ending at `last` (negative = improving for time/place). None if <2 points."""
    d = series_df[series_df["season"] > last - window].dropna(subset=[col])
    if d["season"].nunique() < 2:
        return None
    return float(np.polyfit(d["season"], d[col], 1)[0])


def multiwindow_acceleration(frames: dict, windows=(10, 5, 2, 1)) -> pd.DataFrame:
    """Per program: improvement rate (s/yr in top-5 time; negative = faster) over
    trailing 10/5/2/1-yr windows, plus acceleration = 2yr-rate minus 10yr-rate
    (negative = improvement is accelerating recently)."""
    s = program_strength_series(frames)
    if s.empty:
        return s
    last = int(s["season"].max())
    rows = []
    for (team, gender), g in s.groupby(["team", "gender"]):
        g = g.sort_values("season")
        rates = {}
        for w in windows:
            if w == 1:
                gg = g.dropna(subset=["top5_s"])
                rates["r1"] = (float(gg["top5_s"].iloc[-1] - gg["top5_s"].iloc[-2])
                               if len(gg) >= 2 else None)
            else:
                rates[f"r{w}"] = _rate(g, "top5_s", last, w)
        if rates.get("r10") is None or rates.get("r2") is None:
            continue
        rows.append({
            "team": team, "gender": gender,
            "rate_10yr": rates.get("r10"), "rate_5yr": rates.get("r5"),
            "rate_2yr": rates.get("r2"), "chg_1yr": rates.get("r1"),
            "accel_2v10": rates["r2"] - rates["r10"],
        })
    return pd.DataFrame(rows).sort_values("accel_2v10")


# --------------------------------------------------------------------------
# coaching changes
# --------------------------------------------------------------------------
def coach_changes(coaches: pd.DataFrame) -> list[dict]:
    """Detect head-coach changes per team/gender from tenures (m/f/both)."""
    if coaches is None or coaches.empty:
        return []
    gmap = {"m": "men", "f": "women", "men": "men", "women": "women"}
    out = []
    for team, g in coaches.groupby("team"):
        for gender in ("men", "women"):
            ten = g[g["gender"].apply(
                lambda x: gmap.get(str(x).lower(), "both") in (gender, "both"))]
            ten = ten.sort_values("start_year")
            prev = None
            for _, r in ten.iterrows():
                if prev is not None and r["coach_name"] != prev:
                    out.append({"team": team, "gender": gender,
                                "change_year": int(r["start_year"]),
                                "prev_coach": prev, "new_coach": r["coach_name"]})
                prev = r["coach_name"]
    return out


def coaching_change_effect(frames: dict, k: int = 3) -> pd.DataFrame:
    """Event study: for each coach change, compare the k seasons before vs the k
    seasons from the change onward — top-5 time, regional place, incoming-class
    arrival caliber (debut time), and % out-of-state recruits."""
    s = program_strength_series(frames).set_index(["team", "gender", "season"])
    cb = champ_season_best(frames["results"]).sort_values(["athlete_id", "season"])
    debut = cb.groupby("athlete_id").head(1)[["athlete_id", "team", "gender", "season", "champ_best_s"]]
    debut = debut.rename(columns={"season": "arrival", "champ_best_s": "debut_s"})
    ath = frames.get("athletes")
    if ath is not None and "home_state" in ath.columns:
        debut = debut.merge(ath[["id", "home_state"]].rename(columns={"id": "athlete_id"}),
                            on="athlete_id", how="left")
    else:
        debut["home_state"] = None

    def _mean(series_idx, team, gender, yrs, col):
        vals = [series_idx.loc[(team, gender, y), col] for y in yrs
                if (team, gender, y) in series_idx.index]
        vals = [v for v in vals if pd.notna(v)]
        return float(np.mean(vals)) if vals else np.nan

    def _recruit(team, gender, yrs):
        d = debut[(debut.team == team) & (debut.gender == gender) & (debut.arrival.isin(yrs))]
        cal = float(d["debut_s"].mean()) if len(d) else np.nan
        known = d[d["home_state"].notna()]
        oos = float(100 * (known["home_state"] != "OH").mean()) if len(known) else np.nan
        return cal, oos

    rows = []
    for c in coach_changes(frames["coaches"]):
        team, gender, y = c["team"], c["gender"], c["change_year"]
        before, after = range(y - k, y), range(y, y + k)
        cal_b, oos_b = _recruit(team, gender, before)
        cal_a, oos_a = _recruit(team, gender, after)
        rows.append({
            **c,
            "top5_before": _mean(s, team, gender, before, "top5_s"),
            "top5_after": _mean(s, team, gender, after, "top5_s"),
            "reg_before": _mean(s, team, gender, before, "regional"),
            "reg_after": _mean(s, team, gender, after, "regional"),
            "arrival_before_s": cal_b, "arrival_after_s": cal_a,
            "oos_before_pct": oos_b, "oos_after_pct": oos_a,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["d_top5_s"] = df["top5_after"] - df["top5_before"]        # neg = faster after
    df["d_regional"] = df["reg_after"] - df["reg_before"]        # neg = better after
    df["d_arrival_s"] = df["arrival_after_s"] - df["arrival_before_s"]  # neg=faster recruits
    df["d_oos_pct"] = df["oos_after_pct"] - df["oos_before_pct"]        # +=more national
    return df


# --------------------------------------------------------------------------
# AIRTIGHT: within-athlete difference-in-differences vs a stable-coach control
# --------------------------------------------------------------------------
def _returner_deltas(cb: pd.DataFrame, teams, gender, pre_years, post_years):
    """Within-athlete best-time change (post_best - pre_best) for athletes on
    `teams` who raced in BOTH windows. Negative = improved. Returns a list."""
    d = cb[(cb["gender"] == gender) & (cb["team"].isin(teams))]
    pre = d[d["season"].isin(pre_years)].groupby("athlete_id")["champ_best_s"].min()
    post = d[d["season"].isin(post_years)].groupby("athlete_id")["champ_best_s"].min()
    both = pre.index.intersection(post.index)
    return [(post[a] - pre[a]) for a in both]


def _boot_did(treated, control, n_boot=2000, seed=0):
    """Bootstrap CI for DiD = mean(treated) - mean(control) over athletes."""
    rng = np.random.default_rng(seed)
    t, c = np.asarray(treated, float), np.asarray(control, float)
    dist = [rng.choice(t, t.size, replace=True).mean()
            - rng.choice(c, c.size, replace=True).mean() for _ in range(n_boot)]
    lo, hi = np.percentile(dist, [5, 95])
    return float(np.mean(t) - np.mean(c)), float(lo), float(hi)


def _stable_controls(cb, chg_by_gender, gender, win, treated_team):
    """Teams (gender) with NO coaching change inside `win`, excluding treated."""
    all_g = set(cb[cb["gender"] == gender]["team"].unique())
    lo, hi = min(win), max(win)
    changed = {t for t, ys in chg_by_gender[gender].items()
               if any(lo <= y <= hi for y in ys)}
    return (all_g - changed) - {treated_team}


def _did_estimate(cb, chg_by_gender, team, gender, pre_years, post_years,
                  min_group, n_boot, seed):
    """DiD for one (possibly placebo) window: treated returners on `team` vs
    stable-coach control returners, over identical pre/post windows."""
    win = set(pre_years) | set(post_years)
    if not win:
        return None
    control_teams = _stable_controls(cb, chg_by_gender, gender, win, team)
    treated = _returner_deltas(cb, [team], gender, pre_years, post_years)
    control = _returner_deltas(cb, list(control_teams), gender, pre_years, post_years)
    out = {"n_treated": len(treated), "n_control": len(control),
           "treated_delta_s": float(np.mean(treated)) if treated else np.nan,
           "control_delta_s": float(np.mean(control)) if control else np.nan}
    if len(treated) >= min_group and len(control) >= min_group:
        did, lo, hi = _boot_did(treated, control, n_boot, seed)
        out.update(did_s=did, ci_lo=lo, ci_hi=hi, sufficient=True,
                   significant=(hi < 0 or lo > 0))
    else:
        out.update(did_s=np.nan, ci_lo=np.nan, ci_hi=np.nan,
                   sufficient=False, significant=False)
    return out


def coaching_change_did(frames: dict, k: int = 3, min_group: int = 5,
                        n_boot: int = 2000) -> pd.DataFrame:
    """Airtight coaching-change effect (within-athlete DiD vs stable-coach control)
    WITH a placebo pre-trend test.

    For each change at year Y:
      real    : pre=[Y-k,Y-1], post=[Y,Y+k-1] (clipped to the coaching regime).
      placebo : a fake change at Y-k -> pre=[Y-2k,Y-k-1], post=[Y-k,Y-1], both
                ENTIRELY before the real change. A near-zero, non-significant
                placebo supports parallel trends (=> the real DiD is credible);
                a significant placebo flags a pre-existing divergence.
    """
    cb = champ_season_best(frames["results"])
    changes = coach_changes(frames["coaches"])
    from collections import defaultdict
    by_tg = defaultdict(list)
    chg_by_gender = defaultdict(lambda: defaultdict(list))
    for c in changes:
        by_tg[(c["team"], c["gender"])].append(c["change_year"])
        chg_by_gender[c["gender"]][c["team"]].append(c["change_year"])

    rows = []
    for c in changes:
        team, gender, Y = c["team"], c["gender"], c["change_year"]
        others = sorted(by_tg[(team, gender)])
        prev = max([y for y in others if y < Y], default=-9999)
        nxt = min([y for y in others if y > Y], default=9999)
        real = _did_estimate(
            cb, chg_by_gender, team, gender,
            [y for y in range(max(Y - k, prev + 1), Y)],
            [y for y in range(Y, min(Y + k, nxt))], min_group, n_boot, seed=0)
        # placebo: two pre-treatment windows immediately before the change
        pb = _did_estimate(
            cb, chg_by_gender, team, gender,
            [y for y in range(max(Y - 2 * k, prev + 1), Y - k)],
            [y for y in range(Y - k, Y)], min_group, n_boot, seed=1)
        row = {"team": team, "gender": gender, "change_year": Y,
               "new_coach": c["new_coach"], **real}
        row["placebo_did_s"] = pb["did_s"]
        row["placebo_significant"] = pb["significant"]
        row["placebo_sufficient"] = pb["sufficient"]
        # verdict: credible only if real is significant AND placebo passes
        if not real["sufficient"]:
            row["verdict"] = "insufficient"
        elif not real["significant"]:
            row["verdict"] = "null"
        elif not pb["sufficient"]:
            row["verdict"] = "significant (pre-trend untested)"
        elif pb["significant"]:
            row["verdict"] = "SUSPECT (pre-trend violation)"
        else:
            row["verdict"] = "CREDIBLE (passes placebo)"
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["sufficient", "did_s"],
                                          ascending=[False, True]).reset_index(drop=True)
