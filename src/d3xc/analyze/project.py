"""Forward roster projection: what it takes to win the NCAC / qualify for
nationals, projected to a target year.

Everything is in course/distance-neutral adjVDOT (relative index; absolute
calibration approximate). For each tracked team we carry the roster forward:
  * returning athletes improve by the measured class-year VDOT gains,
  * 4th-year athletes graduate,
  * each new season adds a freshman class at the team's historical arrival
    caliber and class size,
then compare the projected top-5 to the tier bars and decompose the gap into
recruiting (arrival caliber) vs development (yearly gain) levers.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from d3xc.analyze import standardize as SZ

VDOT_PER_5K_SEC = 6.5   # ~1 VDOT point ≈ 6-7 sec over 5k (near D3 range)


def _season_vdot_with_class(adf):
    sv = SZ.athlete_season_vdot(adf).sort_values(["athlete_id", "season"])
    sv["yr"] = sv.groupby("athlete_id").cumcount() + 1
    sv["prev"] = sv.groupby("athlete_id")["adj_vdot"].shift(1)
    sv["gain"] = sv["adj_vdot"] - sv["prev"]
    return sv


def class_gains(sv) -> dict:
    """Mean adjVDOT gain arriving at year k (2,3,4), per gender."""
    g = sv.dropna(subset=["gain"]).groupby(["gender", "yr"])["gain"].mean()
    return g.to_dict()


def team_profiles(sv) -> pd.DataFrame:
    """Per team/gender: arrival caliber (median yr1 adjVDOT) and class size."""
    rows = []
    for (team, gender), d in sv.groupby(["team", "gender"]):
        fr = d[d["yr"] == 1]
        if fr.empty:
            continue
        per_year = fr.groupby("season").size()
        rows.append({"team": team, "gender": gender,
                     "arrival_vdot": float(fr["adj_vdot"].median()),
                     "class_size": int(round(per_year.median())) or 1,
                     "dev_gain_2": float(d[d.yr == 2]["gain"].mean())})
    return pd.DataFrame(rows)


def _project(pool, gender, gains, arrival, class_size, start, to):
    """Return {year: projected top-5 adjVDOT} for years start+1..to."""
    roster = list(pool)                       # [(adj_vdot, yr)]
    default = np.nanmean([v for (gg, k), v in gains.items() if gg == gender]) or 0.0
    out = {}
    for year in range(start + 1, to + 1):
        nxt = []
        for v, yr in roster:
            if yr >= 4:
                continue                      # graduated
            g = gains.get((gender, yr + 1), default)
            nxt.append((v + g, yr + 1))
        nxt += [(arrival, 1)] * class_size
        roster = nxt
        top = sorted((v for v, _ in roster), reverse=True)[:5]
        out[year] = float(np.mean(top)) if len(top) >= 5 else np.nan
    return out


def tier_bars(frames, adf) -> dict:
    """Win-NCAC and qualify-nationals bars in adjVDOT, per gender (recent medians)."""
    tl = SZ.vdot_tier_levels(frames, adf)
    strength = SZ.team_standardized_strength(frames, adf)
    pl = frames["placements"]
    nat = pl[pl["meet_kind"] == "national"].dropna(subset=["team_place"])
    bars = {}
    for gender in ("men", "women"):
        ncac = tl[(tl.tier == "Win NCAC") & (tl.gender == gender)]["adj_vdot"]
        # qualify bar = weakest tracked qualifier's season strength, median over years
        q = []
        for season, g in nat[nat.gender == gender].groupby("season"):
            quals = set(g["team"])
            s = strength[(strength.gender == gender) & (strength.season == season)
                         & (strength.team.isin(quals))]["team_vdot"]
            if len(s):
                q.append(s.min())
        bars[gender] = {"win_ncac": float(ncac.median()) if len(ncac) else np.nan,
                        "qualify": float(np.median(q)) if q else np.nan}
    return bars


def _prep(frames):
    """Shared prep used by project + scenarios."""
    adf = SZ.course_adjusted_performances(frames["results"])
    sv = _season_vdot_with_class(adf)
    return adf, sv, class_gains(sv), team_profiles(sv).set_index(["team", "gender"])


def project_scenario(frames, team, gender, *, arrival=None, dev_boost=0.0,
                     class_size=None, to_year=2029, prep=None):
    """Projected top-5 adjVDOT per year under recruiting/development levers.

    arrival: override incoming-class caliber (adjVDOT). None = historical.
    dev_boost: add this many adjVDOT points to every class-year gain (development).
    class_size: override recruits per class. None = historical.
    """
    _, sv, gains, profiles = prep or _prep(frames)
    if dev_boost:
        gains = {k: v + dev_boost for k, v in gains.items()}
    prof = profiles.loc[(team, gender)]
    last = int(sv["season"].max())
    d = sv[(sv["season"] == last) & (sv["team"] == team) & (sv["gender"] == gender)]
    pool = list(zip(d["adj_vdot"], d["yr"]))
    A = prof["arrival_vdot"] if arrival is None else arrival
    cs = int(prof["class_size"]) if class_size is None else class_size
    return _project(pool, gender, gains, A, cs, last, to_year)


def solve_lever(frames, team, gender, target, by_year, *, lever="arrival",
                dev_boost=0.0, prep=None):
    """Minimal recruiting caliber (arrival adjVDOT) or development boost to hit
    `target` top-5 adjVDOT by `by_year`. None if unreachable in a sane range."""
    prep = prep or _prep(frames)
    lo, hi = (45.0, 75.0) if lever == "arrival" else (0.0, 12.0)

    def val(x):
        kw = {"arrival": x} if lever == "arrival" else {"dev_boost": dev_boost + x}
        if lever == "arrival":
            kw["dev_boost"] = dev_boost
        return project_scenario(frames, team, gender, to_year=by_year, prep=prep,
                                **kw)[by_year]

    if val(hi) < target:
        return None
    for _ in range(45):
        mid = 0.5 * (lo + hi)
        if val(mid) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def coach_actions(frames, team, gender, *, prep=None, proj=None,
                  qualify=67.1, to_year=2029):
    """Coach-facing prescription: minimal recruiting (arrival adjVDOT) and/or
    development (adjVDOT/yr) to (a) win the conference title (beat the strongest
    rival's projection) by 2028 & 2029, and (b) qualify for nationals by 2029.
    """
    prep = prep or _prep(frames)
    proj = project_teams(frames, to_year=to_year) if proj is None else proj
    row = proj[(proj["team"] == team) & (proj["gender"] == gender)].iloc[0]
    conf = row["conference"]
    others = proj[(proj["conference"] == conf) & (proj["gender"] == gender)
                  & (proj["team"] != team)]
    title_bar = {y: (float(others[f"proj_{y}"].max()) if len(others) else float("nan"))
                 for y in range(2026, to_year + 1)}
    out = {"team": team, "gender": gender, "conference": conf,
           "cur_arrival": float(row["arrival_vdot"]),
           "title_bar": title_bar, "qualify_bar": qualify, "title": {}}
    for y in (to_year - 1, to_year):
        tb = title_bar[y] + 0.3                       # must exceed the rival
        out["title"][y] = {
            "bar": title_bar[y],
            "recruit": solve_lever(frames, team, gender, tb, y, lever="arrival", prep=prep),
            "develop": solve_lever(frames, team, gender, tb, y, lever="dev", prep=prep)}
    out["qualify_recruit"] = solve_lever(frames, team, gender, qualify, to_year,
                                         lever="arrival", prep=prep)
    out["qualify_develop"] = solve_lever(frames, team, gender, qualify, to_year,
                                         lever="dev", prep=prep)
    return out


def project_teams(frames, teams=None, to_year=2029) -> pd.DataFrame:
    adf = SZ.course_adjusted_performances(frames["results"])
    sv = _season_vdot_with_class(adf)
    gains = class_gains(sv)
    profiles = team_profiles(sv).set_index(["team", "gender"])
    strength = SZ.team_standardized_strength(frames, adf)
    bars = tier_bars(frames, adf)
    last = int(sv["season"].max())

    rows = []
    for (team, gender), d in sv[sv["season"] == last].groupby(["team", "gender"]):
        if teams and team not in teams:
            continue
        if (team, gender) not in profiles.index:
            continue
        prof = profiles.loc[(team, gender)]
        pool = list(zip(d["adj_vdot"], d["yr"]))
        cur = strength[(strength.team == team) & (strength.gender == gender)
                       & (strength.season == last)]["team_vdot"]
        cur = float(cur.iloc[0]) if len(cur) else np.nan
        proj = _project(pool, gender, gains, prof["arrival_vdot"],
                        int(prof["class_size"]), last, to_year)
        b = bars[gender]
        row = {"team": team, "gender": gender, "cur_vdot": cur,
               "arrival_vdot": prof["arrival_vdot"], "class_size": int(prof["class_size"]),
               "win_ncac_bar": b["win_ncac"], "qualify_bar": b["qualify"]}
        for y in range(last + 1, to_year + 1):
            row[f"proj_{y}"] = proj.get(y, np.nan)
        row["gap_to_qualify_2029"] = b["qualify"] - proj.get(to_year, np.nan)
        rows.append(row)
    out = pd.DataFrame(rows)
    # attach conference from teams table
    conf = frames["teams"].set_index("name")["conference"].to_dict()
    if not out.empty:
        out["conference"] = out["team"].map(conf)
    return out
