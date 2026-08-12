"""Tests for national-context analysis and tracked/untracked separation."""
import pytest

from d3xc import config
from d3xc.analyze import national as N
from d3xc.analyze import development as D
from d3xc.analyze.metrics import load_frames

pytestmark = pytest.mark.skipif(not config.DB_PATH.exists(), reason="no DB")


def test_national_teams_are_untracked_and_excluded_from_ohio_stats():
    f = load_frames()
    teams = f["teams"]
    assert "tracked" in teams.columns
    assert int(teams["tracked"].sum()) == 24          # OAC + full NCAC members
    assert int((~teams["tracked"]).sum()) > 50        # national-context teams added
    # national teams must NOT appear in the Ohio development analysis
    eff = D.program_development_effect(f["results"])
    national_names = set(teams[~teams["tracked"]]["name"])
    assert not (set(eff["team"]) & national_names)


def test_ohio_at_nationals_structure():
    f = load_frames()
    oa = N.ohio_at_nationals(f)
    assert {"season", "gender", "field_teams", "best_ohio_place",
            "national_champion"}.issubset(oa.columns)
    # national fields are ~32 teams
    assert oa["field_teams"].max() >= 30


def test_all_americans_are_top40_and_ohio():
    f = load_frames()
    aa = N.all_americans(f, cutoff=40, ohio_only=True)
    if not aa.empty:
        assert (aa["place_overall"] <= 40).all()
        national = set(f["teams"][~f["teams"]["tracked"]]["name"])
        assert not (set(aa["team"]) & national)      # only Ohio programs
