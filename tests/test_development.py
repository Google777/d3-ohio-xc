"""Tests for college development analysis and the curated HS-marks pipeline."""
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d3xc.analyze import development as D
from d3xc.analyze.metrics import load_frames
from d3xc.scrape.records import RaceResult
from d3xc.store import loaders
from d3xc.store.db import Team, init_db


def _results(rows):
    cols = ["athlete_id", "athlete_name", "team", "gender", "season",
            "meet_name", "meet_date", "distance_m", "mark_seconds"]
    return pd.DataFrame(rows, columns=cols)


def _improving_squad():
    """6 athletes over 3 seasons, all getting faster year over year (men, 8k)."""
    rows = []
    for aid in range(1, 7):
        for i, season in enumerate([2022, 2023, 2024]):
            secs = 1600.0 - i * 20 + aid  # improves 20s/yr
            rows.append((aid, f"A{aid}", "Alpha", "men", season,
                         f"{season} Meet", f"{season}-10-01", 8000, secs))
    r = _results(rows)
    r["conference"] = "OAC"
    return r


def test_class_transition_improvement_positive():
    ct = D.class_transition_stats(_improving_squad())
    m = ct[ct.gender == "men"].set_index("transition")["mean_improve_s"]
    assert m["yr1→yr2"] > 0 and m["yr2→yr3"] > 0     # squad improves each year


def test_champ_season_best_prefers_8k_and_uses_riegel():
    from d3xc.analyze import development as D
    from d3xc.scrape.timeutil import riegel_project
    # athlete A: same season has a fast 5k AND an 8k -> the 8k sets the mark
    # athlete B: only a 5k -> Riegel-projected (slower than linear pace*8)
    rows = [
        (1, "A", "Alpha", "men", 2022, "M1", "2022-09-01", 5000, 900.0),   # 15:00 5k
        (1, "A", "Alpha", "men", 2022, "M2", "2022-10-01", 8000, 1490.0),  # 24:50 8k
        (2, "B", "Alpha", "men", 2022, "M1", "2022-09-01", 5000, 900.0),   # only a 5k
    ]
    res = _results(rows)
    cb = D.champ_season_best(res).set_index("athlete_id")
    assert cb.loc[1, "from_champ"]                      # A uses actual 8k
    assert abs(cb.loc[1, "champ_best_s"] - 1490.0) < 1e-6
    assert not cb.loc[2, "from_champ"]                  # B converted
    riegel = riegel_project(900.0, 5000, 8000)
    assert abs(cb.loc[2, "champ_best_s"] - riegel) < 1e-6
    assert riegel > 900.0 * (8000 / 5000)              # slower than linear pace


def test_program_development_effect_runs():
    eff = D.program_development_effect(_improving_squad(), min_athletes=5)
    assert not eff.empty
    assert "dev_effect_s" in eff.columns
    assert (eff["mean_improve_s"] > 0).all()          # improving squad


def test_rolling_team_projection_runs():
    from d3xc.lactic import power as Pw
    rt = Pw.rolling_team_projection(_improving_squad(), window=3, top_n=5)
    assert not rt.empty
    row = rt[rt.team == "Alpha"].iloc[0]
    assert 1400 < row["team_roll_time_sec"] < 1700   # sane 8k team avg


def test_rolling_smooths_and_flags_volatility():
    from d3xc.analyze import stats as S
    # one team, top5 alternates wildly but trends down; regional steady
    seasons = [2016, 2017, 2018, 2019, 2021, 2022]
    raw = [1600, 1660, 1560, 1620, 1500, 1560]        # swingy but declining
    scoring = pd.DataFrame({
        "team": "Alpha", "conference": "OAC", "gender": "men",
        "season": seasons, "top5_avg": raw})
    placements = pd.DataFrame({
        "team": "Alpha", "gender": "men", "season": seasons,
        "meet_kind": "regional", "team_place": [12, 11, 10, 10, 8, 7]})
    frames = {"results": pd.DataFrame(), "placements": placements}
    # monkeypatch team_scoring_by_season via the private metric builder input:
    import d3xc.analyze.stats as st
    orig = st.team_scoring_by_season
    st.team_scoring_by_season = lambda _r: scoring
    try:
        rm = S.rolling_program_metrics(frames, window=3)
        # rolling series is smoother than raw (smaller successive diffs on avg)
        raw_swing = rm["top5_avg"].diff().abs().mean()
        roll_swing = rm["roll_top5"].diff().abs().mean()
        assert roll_swing < raw_swing
        rc = S.rolling_change(frames, window=3, min_seasons=4)
        row = rc.iloc[0]
        assert row["roll_time_change_s"] < 0          # net improvement
        assert row["mean_yoy_swing_s"] > 0            # volatility captured
    finally:
        st.team_scoring_by_season = orig


@pytest.fixture
def sf():
    eng = create_engine("sqlite://", future=True)
    init_db(eng)
    return eng, sessionmaker(bind=eng, future=True, expire_on_commit=False)


def test_hs_marks_csv_loader(tmp_path, sf):
    eng, Session = sf
    csv = tmp_path / "hs.csv"
    csv.write_text(
        "# comment\n"
        "athlete_name,college_team,gender,event,mark,hs_grad_year,source\n"
        "Alex Miller,Mount Union,men,3200m,9:35.2,2019,test\n",
        encoding="utf-8")
    with Session() as s:
        s.add(Team(name="Mount Union", conference="OAC"))
        s.commit()
        # college result so the athlete exists to link to
        loaders.load_results(s, [RaceResult(
            team="Mount Union", gender="men", season=2020, athlete_name="Alex Miller",
            tfrrs_athlete_id=None, meet_name="M", meet_date="2020-10-01",
            distance_m=8000, mark_seconds=1500.0)])
        s.commit()
        n = loaders.load_hs_marks_csv(s, path=csv)
        s.commit()
    assert n == 1
    f = load_frames(eng)
    hs = f["hs"]
    assert len(hs) == 1
    assert abs(hs.iloc[0]["mark_seconds"] - (9 * 60 + 35.2)) < 1e-6
    assert hs.iloc[0]["match_confidence"] == 1.0
