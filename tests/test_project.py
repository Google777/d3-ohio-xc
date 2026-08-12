"""Tests for the roster projection, scenario levers, and coach prescriptions."""
import pytest

from d3xc import config
from d3xc.analyze import project as PJ

pytestmark = pytest.mark.skipif(not config.DB_PATH.exists(), reason="no DB")


def _frames():
    from d3xc.analyze.metrics import load_frames
    return load_frames()


def test_project_teams_multiyear_and_conferences():
    f = _frames()
    p = PJ.project_teams(f, to_year=2029)
    assert {"cur_vdot", "proj_2026", "proj_2029", "conference"}.issubset(p.columns)
    # realignment must be reflected: JCU in NCAC, Allegheny/Hiram not
    jcu = p[(p.team == "John Carroll") & (p.gender == "men")]
    assert not jcu.empty and jcu.iloc[0]["conference"] == "NCAC"
    assert (p[p.conference == "NCAC"]["team"] != "Allegheny").all()


def test_scenario_levers_monotonic():
    f = _frames()
    prep = PJ._prep(f)
    base = PJ.project_scenario(f, "Kenyon", "men", prep=prep)[2029]
    more_recruit = PJ.project_scenario(f, "Kenyon", "men", arrival=prep[3].loc[
        ("Kenyon", "men")]["arrival_vdot"] + 4, prep=prep)[2029]
    more_dev = PJ.project_scenario(f, "Kenyon", "men", dev_boost=1.5, prep=prep)[2029]
    assert more_recruit > base          # better recruiting -> stronger
    assert more_dev > base              # more development -> stronger


def test_solve_lever_reaches_target():
    f = _frames()
    prep = PJ._prep(f)
    target = 64.0
    a = PJ.solve_lever(f, "Denison", "men", target, 2029, lever="arrival", prep=prep)
    assert a is not None
    got = PJ.project_scenario(f, "Denison", "men", arrival=a, prep=prep)[2029]
    assert abs(got - target) < 0.5      # solved to the target


def test_coach_actions_structure():
    f = _frames()
    act = PJ.coach_actions(f, "Kenyon", "men")
    assert act["conference"] == "NCAC"
    assert 2028 in act["title"] and 2029 in act["title"]
    assert "qualify_recruit" in act and "qualify_develop" in act
