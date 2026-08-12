"""Tests for the LacTiC ML layer: ratings, programs, projection."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d3xc import config
from d3xc.analyze.metrics import load_frames
from d3xc.lactic import programs as P
from d3xc.lactic import ratings as R
from d3xc.scrape.records import RaceResult
from d3xc.store import loaders
from d3xc.store.db import Team, init_db


@pytest.fixture
def sf():
    eng = create_engine("sqlite://", future=True)
    init_db(eng)
    return eng, sessionmaker(bind=eng, future=True, expire_on_commit=False)


def _add_team(session, name, conf="OAC"):
    session.add(Team(name=name, conference=conf))


def _races(team, names_paces, season, meets):
    """Build RaceResult rows: each athlete runs every meet; meets add difficulty."""
    out = []
    for meet_name, difficulty in meets:
        for name, pace in names_paces:
            out.append(RaceResult(
                team=team, gender="men", season=season, athlete_name=name,
                tfrrs_athlete_id=None, meet_name=meet_name,
                meet_date=f"{season}-10-01", distance_m=8000,
                mark_seconds=(pace + difficulty) * 8.0,
            ))
    return out


def test_ratings_monotonic_and_meet_adjusted(sf):
    eng, Session = sf
    # true speeds (sec/km); meet 2 is a "hard course" (+6 to everyone)
    speeds = [("A", 180), ("B", 183), ("C", 186), ("D", 189), ("E", 192), ("F", 195)]
    meets = [("Flat Open", 0.0), ("Hilly Regional", 6.0), ("Fast Invite", -3.0)]
    with Session() as s:
        _add_team(s, "Alpha")
        s.commit()
        loaders.load_results(s, _races("Alpha", speeds, 2020, meets))
        s.commit()

    ar = R.compute_athlete_ratings(load_frames(eng)["results"])
    assert ar["meet_adjusted"].all()
    ordered = ar.sort_values("adj_pace_sec_per_km")["athlete_name"].tolist()
    assert ordered == ["A", "B", "C", "D", "E", "F"]  # true speed order recovered
    # rating decreases as adj pace increases; rank 1 is the fastest
    top = ar.sort_values("rating", ascending=False).iloc[0]
    assert top["athlete_name"] == "A"
    assert top["rank_in_group"] == 1


def test_program_ranking_and_tiers(sf):
    eng, Session = sf
    fast = [(f"AF{i}", 180 + i) for i in range(6)]     # Alpha: fast squad
    slow = [(f"BS{i}", 200 + i) for i in range(6)]     # Bravo: slow squad
    meets = [("Meet1", 0.0), ("Meet2", 4.0)]
    with Session() as s:
        _add_team(s, "Alpha", "OAC")
        _add_team(s, "Bravo", "OAC")
        s.commit()
        loaders.load_results(s, _races("Alpha", fast, 2020, meets))
        loaders.load_results(s, _races("Bravo", slow, 2020, meets))
        s.commit()

    ar = R.compute_athlete_ratings(load_frames(eng)["results"])
    strength = P.program_strength(ar)
    rank = P.rank_programs(strength, "men", 2020)
    assert rank.iloc[0]["team"] == "Alpha"          # faster squad ranked #1
    assert rank.iloc[0]["program_adj_pace"] < rank.iloc[1]["program_adj_pace"]


def test_trajectory_sign(sf):
    eng, Session = sf
    meets = [("M1", 0.0), ("M2", 3.0)]
    with Session() as s:
        _add_team(s, "Alpha", "OAC")
        s.commit()
        # squad gets faster each season -> negative pace slope (improving)
        for season, shift in [(2020, 10), (2021, 5), (2022, 0)]:
            squad = [(f"A{i}", 185 + i + shift) for i in range(6)]
            loaders.load_results(s, _races("Alpha", squad, season, meets))
        s.commit()

    ar = R.compute_athlete_ratings(load_frames(eng)["results"])
    traj = P.program_trajectory(P.program_strength(ar))
    row = traj[traj["team"] == "Alpha"].iloc[0]
    assert row["pace_slope"] < 0          # pace dropping = improving
    assert row["improvement_rate"] > 0


@pytest.mark.skipif(
    not config.DB_PATH.exists(),
    reason="no DB; run scripts/seed_sample.py to enable projection test",
)
def test_projection_has_skill():
    from d3xc.lactic.projection import run_projection
    res = run_projection()
    assert res.n_samples > 20
    assert res.cv_mae < res.baseline_mae          # beats persistence baseline
    assert not res.over_under.empty
    # over_under sorted ascending by residual -> top row is an overperformer
    assert res.over_under.iloc[0]["residual"] < 0
    assert set(["prev_adj_pace", "predicted_pace", "actual_pace"]).issubset(
        res.over_under.columns
    )
