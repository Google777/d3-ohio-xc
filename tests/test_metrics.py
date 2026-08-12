"""Metrics tests on a controlled in-memory dataset."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d3xc.analyze import metrics as m
from d3xc.scrape.records import HSMark, MeetTeamPlacement, RaceResult
from d3xc.store import loaders
from d3xc.store.db import Team, init_db


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", future=True)  # in-memory
    init_db(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _seed(session_factory):
    with session_factory() as s:
        s.add(Team(name="Mount Union", conference="OAC"))
        s.add(Team(name="Kenyon", conference="NCAC"))
        s.commit()

        results = []
        # Mount Union man improves 1500 -> 1420 over 2020..2022 (7 athletes/yr)
        for season, base in [(2020, 1560), (2021, 1500), (2022, 1450)]:
            for i in range(7):
                results.append(RaceResult(
                    team="Mount Union", gender="men", season=season,
                    athlete_name=f"Runner {i}", tfrrs_athlete_id=None,
                    meet_name=f"{season} Meet", meet_date=f"{season}-10-01",
                    distance_m=8000, mark_seconds=base + i * 8,
                ))
        loaders.load_results(s, results)
        s.commit()

        placements = [
            MeetTeamPlacement("Conf", "2020-11-01", 2020, "men", "Mount Union", 5, 120, "conference"),
            MeetTeamPlacement("Conf", "2022-11-01", 2022, "men", "Mount Union", 1, 40, "conference"),
            MeetTeamPlacement("Reg", "2020-11-14", 2020, "men", "Mount Union", 12, 300, "regional"),
            MeetTeamPlacement("Reg", "2022-11-14", 2022, "men", "Mount Union", 4, 130, "regional"),
        ]
        loaders.load_team_placements(s, placements)
        s.commit()

        hs = [HSMark("Runner 0", "Mount Union", "men", "3200m", 600.0, 2020,
                     "synthetic", 0.95)]
        loaders.load_hs_marks(s, hs)
        s.commit()


def test_team_scoring(engine, session_factory):
    _seed(session_factory)
    f = m.load_frames(engine)
    sc = m.team_scoring_by_season(f["results"])
    mu = sc[sc["team"] == "Mount Union"].sort_values("season")
    assert len(mu) == 3
    # top5 avg should improve (decrease) each season
    vals = mu["top5_avg"].tolist()
    assert vals[0] > vals[1] > vals[2]
    # 7 athletes so top7 avg is present
    assert mu["top7_avg"].notna().all()
    # pack spread = (5th - 1st) = 4*8 = 32s
    assert abs(mu.iloc[0]["spread_1_5"] - 32.0) < 1e-6


def test_most_improved_athletes(engine, session_factory):
    _seed(session_factory)
    f = m.load_frames(engine)
    mi = m.most_improved_athletes(f["results"])
    assert not mi.empty
    # each runner debuts 2020 at base+.., best in 2022 -> ~110s faster
    row = mi.iloc[0]
    assert row["improvement_seconds"] > 100
    assert row["debut_season"] == 2020


def test_most_improved_teams(engine, session_factory):
    _seed(session_factory)
    f = m.load_frames(engine)
    mt = m.most_improved_teams(f["placements"], "regional")
    assert mt.iloc[0]["places_gained"] == 8  # 12 -> 4


def test_conference_wins(engine, session_factory):
    _seed(session_factory)
    f = m.load_frames(engine)
    cw = m.conference_wins(f["placements"])
    assert cw.iloc[0]["team"] == "Mount Union"
    assert cw.iloc[0]["conference_titles"] == 1


def test_hs_to_college(engine, session_factory):
    _seed(session_factory)
    f = m.load_frames(engine)
    h2c = m.hs_to_college(f["results"], f["hs"], min_confidence=0.6)
    assert not h2c.empty
    # HS 3200m pace (600/3.2=187.5) vs college 8k pace (~1450/8=181) -> improvement
    assert h2c.iloc[0]["pace_improvement_pct"] > 0


def test_load_frames_empty_placements_have_columns(engine, session_factory):
    """Regression: a scrape with no team placements must not break load_frames.

    read_sql returns schema columns for empty tables; load_frames must still
    attach team/conference so dashboard filters don't KeyError.
    """
    with session_factory() as s:
        s.add(Team(name="Solo", conference="OAC"))
        s.commit()
        loaders.load_results(s, [RaceResult(
            team="Solo", gender="men", season=2024, athlete_name="X",
            tfrrs_athlete_id=None, meet_name="M", meet_date="2024-10-01",
            distance_m=8000, mark_seconds=1500.0)])
        s.commit()
    f = m.load_frames(engine)
    assert f["placements"].empty
    assert "conference" in f["placements"].columns
    assert "team" in f["placements"].columns
    # the shared dashboard filter pattern must work without raising
    pg = f["placements"][
        (f["placements"]["gender"] == "men")
        & (f["placements"]["conference"].isin(["OAC"]))
    ]
    assert pg.empty
