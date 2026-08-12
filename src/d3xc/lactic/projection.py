"""LacTiC development model — project next-season pace, flag over/under-performers.

We frame development as a supervised problem over season-to-season transitions:

    next_season_adj_pace  ~  f(prev_adj_pace, experience, recent_trend,
                               team_strength, HS mark, gender, gap)

A GradientBoostingRegressor learns the typical development curve (freshmen
improve most, seniors plateau, regression toward the mean, stronger programs
develop athletes differently). The model's value for *analysis* is the residual:

    residual = actual_next_pace - predicted_next_pace         (out-of-fold)

A large NEGATIVE residual = ran much faster than the model expected given their
profile = "most improved versus expectation" — a cleaner development signal than
raw improvement, which just rewards slow freshmen.

Honesty notes:
  * residuals use cross_val_predict (out-of-fold) to avoid leakage.
  * on synthetic seed data the error numbers are illustrative only.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import KFold, cross_val_predict, cross_val_score

from d3xc.analyze.metrics import _event_to_km, load_frames
from d3xc.lactic.programs import program_strength
from d3xc.lactic.ratings import compute_athlete_ratings

FEATURES = [
    "prev_adj_pace", "seasons_run", "recent_trend",
    "team_strength_prev", "hs_pace", "has_hs", "gap_years", "is_men",
]


@dataclasses.dataclass
class ProjectionResult:
    n_samples: int
    cv_mae: float
    baseline_mae: float           # persistence baseline (predict prev pace)
    skill_vs_baseline: float      # fraction of baseline MAE removed
    importances: dict
    over_under: pd.DataFrame       # most-improved-vs-expected (residual asc)
    projections: pd.DataFrame      # returning athletes: predicted next season


def _hs_pace_lookup(hs: pd.DataFrame) -> dict:
    if hs is None or hs.empty:
        return {}
    h = hs.copy()
    h["km"] = h["event"].map(_event_to_km)
    h["pace"] = h["mark_seconds"] / h["km"]
    best = h.groupby(["athlete_name", "college_team", "gender"])["pace"].min()
    return best.to_dict()


def build_training_frame(engine=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (transitions, athlete_ratings). transitions has FEATURES+target+meta."""
    frames = load_frames(engine)
    ar = compute_athlete_ratings(frames["results"])
    if ar.empty:
        return pd.DataFrame(), ar

    ps = program_strength(ar)[["team", "gender", "season", "program_adj_pace"]]
    ps = ps.rename(columns={"program_adj_pace": "team_strength_prev"})
    hs_lookup = _hs_pace_lookup(frames.get("hs"))

    ar = ar.sort_values(["athlete_id", "season"])
    rows = []
    for aid, g in ar.groupby("athlete_id"):
        g = g.sort_values("season").reset_index(drop=True)
        for i in range(1, len(g)):
            prev, nxt = g.loc[i - 1], g.loc[i]
            recent_trend = (
                prev["adj_pace_sec_per_km"] - g.loc[i - 2]["adj_pace_sec_per_km"]
                if i >= 2 else 0.0
            )
            key = (prev["athlete_name"], prev["team"], prev["gender"])
            rows.append({
                "athlete_id": aid,
                "athlete_name": prev["athlete_name"],
                "team": prev["team"],
                "gender": prev["gender"],
                "from_season": int(prev["season"]),
                "to_season": int(nxt["season"]),
                "prev_adj_pace": prev["adj_pace_sec_per_km"],
                "seasons_run": i,               # experience proxy (1=after FR yr)
                "recent_trend": recent_trend,
                "hs_pace": hs_lookup.get(key, np.nan),
                "has_hs": 1 if key in hs_lookup else 0,
                "gap_years": int(nxt["season"] - prev["season"]),
                "is_men": 1 if prev["gender"] == "men" else 0,
                "target": nxt["adj_pace_sec_per_km"],
            })
    trans = pd.DataFrame(rows)
    if trans.empty:
        return trans, ar
    trans = trans.merge(
        ps, left_on=["team", "gender", "from_season"],
        right_on=["team", "gender", "season"], how="left",
    ).drop(columns=["season"])
    # impute missing team strength / hs pace with column medians, then 0 for
    # columns that are entirely missing (e.g. HS marks not scraped).
    for col in ("team_strength_prev", "hs_pace"):
        trans[col] = trans[col].fillna(trans[col].median()).fillna(0.0)
    return trans, ar


def run_projection(engine=None, random_state: int = 0) -> ProjectionResult:
    trans, ar = build_training_frame(engine)
    if trans.empty or len(trans) < 20:
        return ProjectionResult(len(trans), float("nan"), float("nan"),
                                float("nan"), {}, pd.DataFrame(), pd.DataFrame())

    X = trans[FEATURES].to_numpy(dtype=float)
    y = trans["target"].to_numpy(dtype=float)
    model = GradientBoostingRegressor(random_state=random_state)

    cv = KFold(n_splits=5, shuffle=True, random_state=random_state)
    cv_mae = -cross_val_score(model, X, y, cv=cv,
                              scoring="neg_mean_absolute_error").mean()
    oof = cross_val_predict(model, X, y, cv=cv)
    baseline_mae = float(np.mean(np.abs(y - trans["prev_adj_pace"].to_numpy())))

    model.fit(X, y)
    importances = dict(sorted(
        zip(FEATURES, model.feature_importances_), key=lambda kv: -kv[1]
    ))

    ou = trans[[
        "athlete_name", "team", "gender", "from_season", "to_season",
        "prev_adj_pace",
    ]].copy()
    ou["actual_pace"] = y
    ou["predicted_pace"] = oof
    ou["residual"] = ou["actual_pace"] - ou["predicted_pace"]
    ou["expected_improvement"] = ou["prev_adj_pace"] - ou["predicted_pace"]
    ou["actual_improvement"] = ou["prev_adj_pace"] - ou["actual_pace"]
    over_under = ou.sort_values("residual").reset_index(drop=True)

    projections = _project_returning(ar, model, engine)

    return ProjectionResult(
        n_samples=len(trans),
        cv_mae=float(cv_mae),
        baseline_mae=baseline_mae,
        skill_vs_baseline=float((baseline_mae - cv_mae) / baseline_mae)
        if baseline_mae else float("nan"),
        importances=importances,
        over_under=over_under,
        projections=projections,
    )


def _project_returning(ar: pd.DataFrame, model, engine) -> pd.DataFrame:
    """Predict next-season pace for athletes active in the final data season."""
    frames = load_frames(engine)
    ps = program_strength(ar)[["team", "gender", "season", "program_adj_pace"]]
    hs_lookup = _hs_pace_lookup(frames.get("hs"))
    last_season = int(ar["season"].max())

    rows = []
    for aid, g in ar.groupby("athlete_id"):
        g = g.sort_values("season").reset_index(drop=True)
        if int(g.iloc[-1]["season"]) != last_season:
            continue  # not a returning athlete (graduated / left)
        last = g.iloc[-1]
        recent_trend = (
            last["adj_pace_sec_per_km"] - g.iloc[-2]["adj_pace_sec_per_km"]
            if len(g) >= 2 else 0.0
        )
        ts = ps[(ps["team"] == last["team"]) & (ps["gender"] == last["gender"])
                & (ps["season"] == last_season)]["program_adj_pace"]
        key = (last["athlete_name"], last["team"], last["gender"])
        rows.append({
            "athlete_name": last["athlete_name"], "team": last["team"],
            "gender": last["gender"], "last_season": last_season,
            "prev_adj_pace": last["adj_pace_sec_per_km"],
            "seasons_run": len(g),
            "recent_trend": recent_trend,
            "team_strength_prev": ts.iloc[0] if len(ts) else np.nan,
            "hs_pace": hs_lookup.get(key, np.nan),
            "has_hs": 1 if key in hs_lookup else 0,
            "gap_years": 1,
            "is_men": 1 if last["gender"] == "men" else 0,
        })
    proj = pd.DataFrame(rows)
    if proj.empty:
        return proj
    for col in ("team_strength_prev", "hs_pace"):
        proj[col] = proj[col].fillna(proj[col].median()).fillna(0.0)
    proj["projected_pace"] = model.predict(proj[FEATURES].to_numpy(dtype=float))
    proj["projected_improvement"] = proj["prev_adj_pace"] - proj["projected_pace"]
    return proj.sort_values("projected_improvement", ascending=False).reset_index(drop=True)
