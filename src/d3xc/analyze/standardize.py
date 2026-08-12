"""Course- and distance-neutral performance standardization.

XC times are confounded by course/terrain/conditions and even varying length.
We fix both:
  1. VDOT (Daniels-Gilbert) maps any (time, distance) to a fitness score, so a
     5k/6k/8k/4-mile all become comparable — handles varying length.
  2. Course adjustment: a ridge model VDOT ~ athlete + meet estimates each meet's
     difficulty (in VDOT points) from runners who raced multiple meets; we
     subtract the meet's deviation to get a neutral-course VDOT.

`adj_vdot` (higher = fitter) is the standardized currency; vdot_to_time converts
a VDOT back to an equivalent time (e.g. a standardized 5k) for readability.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import Ridge
from sklearn.preprocessing import OneHotEncoder

from d3xc.scrape.tfrrs import classify_meet_kind


def vdot_from_time(t_seconds: float, dist_m: float) -> float:
    """Daniels-Gilbert VDOT from a race time (s) and distance (m)."""
    if not t_seconds or not dist_m or t_seconds <= 0 or dist_m <= 0:
        return np.nan
    t = t_seconds / 60.0
    v = dist_m / t                                   # m/min
    pct = (0.8 + 0.1894393 * np.exp(-0.012778 * t)
           + 0.2989558 * np.exp(-0.1932605 * t))
    vo2 = -4.60 + 0.182258 * v + 0.000104 * v * v
    return float(vo2 / pct)


def vdot_to_time(vdot: float, dist_m: float) -> float:
    """Invert VDOT -> equivalent time (s) at a distance (VDOT is monotone in t)."""
    if not np.isfinite(vdot):
        return np.nan
    lo, hi = 60.0, 3600.0                            # 1 min .. 60 min
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if vdot_from_time(mid, dist_m) > vdot:       # faster time -> higher VDOT
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def course_adjusted_performances(results: pd.DataFrame, alpha: float = 5.0,
                                 tracked_only: bool = True,
                                 reference: str = "championship") -> pd.DataFrame:
    """Add `vdot` and course-neutral `adj_vdot` to each XC performance.

    reference: neutral course the VDOT is expressed on.
      "championship" (default) — mean of conference/regional/national courses, so
        adj_vdot ≈ a realistic championship-course VDOT (calibrated for VDOT->5k).
      "all" — mean of every meet (includes fast flat 5k invites; inflates).
    """
    df = results.dropna(subset=["mark_seconds", "distance_m"]).copy()
    if tracked_only and "tracked" in df.columns:
        df = df[df["tracked"]]
    if df.empty:
        return df
    df["vdot"] = [vdot_from_time(t, d) for t, d in zip(df["mark_seconds"], df["distance_m"])]
    df = df[(df["vdot"] > 25) & (df["vdot"] < 80)]   # drop implausible/parse errors
    df["meet_key"] = df["season"].astype(str) + "|" + df["meet_name"].astype(str)

    parts = []
    for gender, g in df.groupby("gender"):
        g = g.copy()
        if g["meet_key"].nunique() >= 2 and g["athlete_id"].nunique() >= 3:
            A = OneHotEncoder(handle_unknown="ignore").fit(g[["athlete_id"]].astype(str))
            M = OneHotEncoder(handle_unknown="ignore").fit(g[["meet_key"]].astype(str))
            X = sparse.hstack([A.transform(g[["athlete_id"]].astype(str)),
                               M.transform(g[["meet_key"]].astype(str))]).tocsr()
            model = Ridge(alpha=alpha, fit_intercept=True).fit(X, g["vdot"].to_numpy(float))
            n_a = A.transform(g[["athlete_id"]].astype(str)).shape[1]
            m_coef = model.coef_[n_a:]
            meet_ids = list(M.categories_[0])
            eff = dict(zip(meet_ids, m_coef))
            # neutral reference course
            if reference == "championship":
                champ = [eff[k] for k in meet_ids
                         if classify_meet_kind(k.split("|", 1)[1]) in
                         ("conference", "regional", "national")]
                ref = float(np.mean(champ)) if champ else float(np.mean(m_coef))
            else:
                ref = float(np.mean(m_coef))
            g["meet_diff"] = g["meet_key"].map(lambda k: eff.get(k, ref))
            g["adj_vdot"] = g["vdot"] - (g["meet_diff"] - ref)
        else:
            g["meet_diff"] = 0.0
            g["adj_vdot"] = g["vdot"]
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def athlete_season_vdot(adf: pd.DataFrame) -> pd.DataFrame:
    """Best (max) course-adjusted VDOT per athlete per season."""
    if adf.empty:
        return adf
    idx = adf.groupby(["athlete_id", "season"])["adj_vdot"].idxmax()
    return adf.loc[idx, ["athlete_id", "athlete_name", "team", "gender",
                         "season", "adj_vdot", "vdot"]].reset_index(drop=True)


def team_top5_vdot_at_meet(adf, season, meet_name, team):
    d = adf[(adf["meet_key"] == f"{season}|{meet_name}") & (adf["team"] == team)]
    top = d.nlargest(5, "adj_vdot")["adj_vdot"]
    return float(top.mean()) if len(top) >= 5 else np.nan


def vdot_tier_levels(frames: dict, adf=None) -> pd.DataFrame:
    """Course+distance-neutral team top-5 adjVDOT for conference champions.

    (National tier omitted: the national meet is under-identified on this scale —
    rotating venue + national-only athletes — use finish place there instead.)
    """
    adf = course_adjusted_performances(frames["results"]) if adf is None else adf
    pl = frames["placements"]
    rows = []
    for conf, pat in [("OAC", "Ohio Athletic|OAC"), ("NCAC", "Coast|NCAC")]:
        d = pl[(pl["meet_kind"] == "conference")
               & pl["meet_name"].str.contains(pat, case=False, na=False)
               & (pl["team_place"] == 1)]
        for _, c in d.iterrows():
            v = team_top5_vdot_at_meet(adf, int(c["season"]), c["meet_name"], c["team"])
            if v == v:
                rows.append({"tier": f"Win {conf}", "gender": c["gender"],
                             "season": int(c["season"]), "team": c["team"], "adj_vdot": v})
    return pd.DataFrame(rows)


def vdot_tier_summary(frames: dict) -> pd.DataFrame:
    """Per gender/tier: median adjVDOT to win + equivalent standardized 5k time."""
    tl = vdot_tier_levels(frames)
    if tl.empty:
        return tl
    g = (tl.groupby(["gender", "tier"])["adj_vdot"]
         .agg(years="count", median_vdot="median", best_vdot="max", worst_vdot="min")
         .reset_index())
    g["equiv_5k_s"] = g["median_vdot"].map(lambda v: vdot_to_time(v, 5000))
    return g


def team_standardized_strength(frames: dict, adf=None) -> pd.DataFrame:
    """Per team/gender/season: top-5 season-best adjVDOT (course+distance neutral)."""
    adf = course_adjusted_performances(frames["results"]) if adf is None else adf
    sv = athlete_season_vdot(adf)
    rows = []
    for (team, gender, season), g in sv.groupby(["team", "gender", "season"]):
        top = g.nlargest(5, "adj_vdot")["adj_vdot"]
        if len(top) >= 5:
            rows.append({"team": team, "gender": gender, "season": int(season),
                         "team_vdot": float(top.mean())})
    return pd.DataFrame(rows).sort_values(["gender", "season", "team_vdot"],
                                          ascending=[True, True, False]).reset_index(drop=True)
