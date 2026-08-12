"""Out-of-sample validation of LacTiC — is it actually predictive?

All tests use only information available BEFORE the race/meet.

1. Pairwise finish-order concordance on held-out (test-season) races: for every
   pair of runners in a race, did the predictor order them the way they actually
   finished? Compared across predictors:
     * pre_elo         - chronological head-to-head Elo (LacTiC v2)
     * prev_best_pace  - career-best pace to date (reactionary baseline)
     * ewma_pace       - recency-weighted pace
     * last_pace       - most recent race pace
     * madj_ewma       - recency-weighted meet-adjusted pace
     * blend           - z(Elo) + z(-best pace)
     * coin flip       - 0.50 reference

2. Team-placement prediction at test-season championships: rank teams by mean
   pre-championship top-5 Elo, compare to actual finish order (Spearman rho).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from d3xc.analyze.metrics import with_pace
from d3xc.scrape.timeutil import parse_meet_date

_LOWER_BETTER = ["prev_best_pace", "ewma_pace", "last_pace", "madj_ewma"]


def _predictors(results: pd.DataFrame) -> pd.DataFrame:
    """Per race row, PRE-race predictors computed only from prior races."""
    df = with_pace(results).dropna(subset=["pace_sec_per_km"]).copy()
    df["date_int"] = df["meet_date"].map(parse_meet_date)
    df["date_int"] = df["date_int"].fillna(df["season"] * 10000 + 1015).astype(int)
    df["race_key"] = (df["season"].astype(str) + "|" + df["gender"] + "|"
                      + df["meet_name"].astype(str))
    df["race_mean"] = df.groupby("race_key")["pace_sec_per_km"].transform("mean")
    df["madj"] = df["pace_sec_per_km"] - df["race_mean"]
    df = df.sort_values(["athlete_id", "date_int"])
    gp = df.groupby("athlete_id")
    df["prev_best_pace"] = gp["pace_sec_per_km"].transform(lambda s: s.expanding().min().shift(1))
    df["ewma_pace"] = gp["pace_sec_per_km"].transform(lambda s: s.ewm(span=3).mean().shift(1))
    df["last_pace"] = gp["pace_sec_per_km"].transform(lambda s: s.shift(1))
    df["madj_ewma"] = gp["madj"].transform(lambda s: s.ewm(span=3).mean().shift(1))
    return df[["athlete_id", "race_key", *(_LOWER_BETTER)]]


def _concordance(pred_higher_better: np.ndarray, place: np.ndarray) -> tuple[int, int]:
    """(concordant_pairs, comparable_pairs) within one race."""
    S = np.sign(pred_higher_better[:, None] - pred_higher_better[None, :])
    P = np.sign(place[None, :] - place[:, None])   # higher pred -> lower place
    iu = np.triu_indices(len(place), k=1)
    su, pu = S[iu], P[iu]
    comparable = (su != 0) & (pu != 0)
    return int(((su == pu) & comparable).sum()), int(comparable.sum())


def _z(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - x.mean()) / sd if sd > 0 else x * 0.0


def pairwise_accuracy(history: pd.DataFrame, results: pd.DataFrame,
                      test_seasons: set[int]) -> dict:
    preds = _predictors(results)
    h = history.merge(preds, on=["athlete_id", "race_key"], how="left")
    h = h[h["season"].isin(test_seasons)]

    names = ["pre_elo", *_LOWER_BETTER, "blend"]
    tot = {n: [0, 0] for n in names}
    for _, race in h.groupby("race_key"):
        place = race["place"].to_numpy()
        c, n = _concordance(race["pre_elo"].to_numpy(), place)
        tot["pre_elo"][0] += c
        tot["pre_elo"][1] += n
        for pcol in _LOWER_BETTER:
            b = race.dropna(subset=[pcol])
            if len(b) >= 2:
                cc, nn = _concordance(-b[pcol].to_numpy(), b["place"].to_numpy())
                tot[pcol][0] += cc
                tot[pcol][1] += nn
        b = race.dropna(subset=["prev_best_pace"])
        if len(b) >= 2:
            score = _z(b["pre_elo"].to_numpy()) + _z(-b["prev_best_pace"].to_numpy())
            cc, nn = _concordance(score, b["place"].to_numpy())
            tot["blend"][0] += cc
            tot["blend"][1] += nn

    out = {"test_seasons": sorted(test_seasons),
           "races": int(h["race_key"].nunique()), "coinflip": 0.5}
    for n in names:
        c, tn = tot[n]
        out[f"{n}_accuracy"] = c / tn if tn else float("nan")
    return out


def team_placement_prediction(history: pd.DataFrame, placements: pd.DataFrame,
                              test_seasons: set[int],
                              kinds=("conference", "regional")) -> dict:
    """Predict team order at test-season championships from pre-meet top-5 Elo."""
    champ = placements[placements["meet_kind"].isin(kinds)
                       & placements["season"].isin(test_seasons)].copy()
    rhos, detail = [], []
    for (season, gender, meet), g in champ.groupby(["season", "gender", "meet_name"]):
        hrace = history[history["race_key"] == f"{season}|{gender}|{meet}"]
        if hrace.empty:
            continue
        pred = (hrace.groupby("team")
                .apply(lambda d: d.nlargest(5, "pre_elo")["pre_elo"].mean()
                       if len(d) >= 3 else np.nan).dropna())
        actual = g.dropna(subset=["team_place"]).set_index("team")["team_place"]
        common = pred.index.intersection(actual.index)
        if len(common) < 3:
            continue
        rho = pd.Series(-pred[common]).corr(pd.Series(actual[common]), method="spearman")
        if pd.notna(rho):
            rhos.append(rho)
            detail.append((int(season), gender, meet[:30], len(common), round(float(rho), 2)))
    return {
        "meets_evaluated": len(rhos),
        "mean_spearman": float(np.mean(rhos)) if rhos else float("nan"),
        "median_spearman": float(np.median(rhos)) if rhos else float("nan"),
        "detail": detail,
    }
