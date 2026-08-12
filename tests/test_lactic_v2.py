"""Tests for LacTiC v2: Elo, PacePower, validation, and deeper stats."""
import numpy as np
import pandas as pd

from d3xc.lactic import elo as E
from d3xc.lactic import power as P
from d3xc.lactic import validate as V
from d3xc.analyze import stats as S


def _results(rows):
    """rows: list of (athlete_id, name, team, gender, season, meet, date, dist, secs)."""
    cols = ["athlete_id", "athlete_name", "team", "gender", "season",
            "meet_name", "meet_date", "distance_m", "mark_seconds"]
    return pd.DataFrame(rows, columns=cols)


def _three_race_ladder():
    """A always beats B beats C, across 3 dated races (men, 8k)."""
    rows = []
    times = {1: 1500.0, 2: 1540.0, 3: 1580.0}  # A,B,C seconds (A fastest)
    for si, (season, date) in enumerate([(2022, "October 1, 2022"),
                                         (2023, "October 1, 2023"),
                                         (2024, "October 1, 2024")]):
        for aid, secs in times.items():
            rows.append((aid, f"Ath{aid}", "Alpha", "men", season,
                         f"{season} Meet", date, 8000, secs + si * 2))
    return _results(rows)


def test_elo_orders_by_strength():
    h = E.compute_elo(_three_race_ladder())
    cr = E.current_ratings(h).set_index("athlete_id")["elo"]
    assert cr[1] > cr[2] > cr[3]          # A > B > C


def test_pace_power_orders_and_projects():
    pp = P.pace_power(_three_race_ladder()).set_index("athlete_id")
    # A fastest -> lowest projected time, highest rating
    assert pp.loc[1, "proj_time_sec"] < pp.loc[2, "proj_time_sec"] < pp.loc[3, "proj_time_sec"]
    assert pp.loc[1, "rating"] > pp.loc[3, "rating"]
    assert 1400 < pp.loc[1, "proj_time_sec"] < 1650   # ~25 min 8k, sane


def test_concordance_pure():
    pred = np.array([3.0, 2.0, 1.0])      # higher = predicted better
    place = np.array([1, 2, 3])           # actual finish (1=best)
    c, n = V._concordance(pred, place)
    assert (c, n) == (3, 3)               # perfectly concordant
    c2, n2 = V._concordance(pred, np.array([3, 2, 1]))
    assert (c2, n2) == (0, 3)             # perfectly discordant


def test_pairwise_accuracy_beats_coin_on_separable_data():
    # bigger fields so pairs exist across test season
    rows = []
    for season, date in [(2022, "October 1, 2022"), (2023, "October 1, 2023")]:
        for aid in range(1, 9):
            rows.append((aid, f"A{aid}", "Alpha", "men", season,
                         f"{season} Meet", date, 8000, 1500.0 + aid * 10))
    res = _results(rows)
    h = E.compute_elo(res)
    acc = V.pairwise_accuracy(h, res, {2023})
    assert acc["ewma_pace_accuracy"] >= 0.9      # separable -> easy
    assert acc["pre_elo_accuracy"] > 0.5


def test_stats_trajectories_have_pvalue():
    from d3xc.analyze.metrics import load_frames  # uses seeded/real DB if present
    # build a tiny frames dict directly instead of DB
    res = _three_race_ladder().assign(conference="OAC")
    frames = {"results": res, "placements": pd.DataFrame(
        columns=["team", "gender", "season", "meet_kind", "team_place",
                 "meet_name", "conference"])}
    traj = S.program_trajectories(frames)
    assert {"reg_p", "time_p"}.issubset(traj.columns)
