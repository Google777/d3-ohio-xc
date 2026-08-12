"""Tests for coaching-change detection and program-dynamics analysis."""
import pandas as pd
import pytest

from d3xc import config
from d3xc.analyze import coaching as C


def test_coach_changes_detection():
    coaches = pd.DataFrame([
        {"team": "Alpha", "gender": "both", "coach_name": "Old", "start_year": 2016, "end_year": 2019},
        {"team": "Alpha", "gender": "both", "coach_name": "New", "start_year": 2020, "end_year": None},
        {"team": "Beta", "gender": "m", "coach_name": "Solo", "start_year": 2016, "end_year": None},
    ])
    changes = C.coach_changes(coaches)
    alpha = [c for c in changes if c["team"] == "Alpha"]
    # one change, applied to BOTH genders
    assert {c["gender"] for c in alpha} == {"men", "women"}
    assert all(c["change_year"] == 2020 and c["prev_coach"] == "Old"
               and c["new_coach"] == "New" for c in alpha)
    # Beta has a single coach -> no change
    assert not [c for c in changes if c["team"] == "Beta"]


@pytest.mark.skipif(not config.DB_PATH.exists(), reason="no DB")
def test_dynamics_run_on_real_data():
    from d3xc.analyze.metrics import load_frames
    f = load_frames()
    acc = C.multiwindow_acceleration(f)
    assert {"rate_10yr", "rate_5yr", "rate_2yr", "accel_2v10"}.issubset(acc.columns)
    ce = C.coaching_change_effect(f, k=3)
    assert {"d_top5_s", "d_regional", "d_arrival_s", "d_oos_pct"}.issubset(ce.columns)
    did = C.coaching_change_did(f, k=3, min_group=5)
    assert {"did_s", "ci_lo", "ci_hi", "sufficient", "significant", "n_treated",
            "n_control", "placebo_did_s", "placebo_significant",
            "placebo_sufficient", "verdict"}.issubset(did.columns)
    suf = did[did.sufficient]
    # CI must bracket the point estimate for every sufficient change
    assert ((suf["ci_lo"] <= suf["did_s"] + 1e-6) & (suf["did_s"] <= suf["ci_hi"] + 1e-6)).all()
    # 'significant' iff CI excludes 0
    assert (suf["significant"] == ((suf["ci_hi"] < 0) | (suf["ci_lo"] > 0))).all()
    # verdict logic: CREDIBLE requires significant real + sufficient, non-sig placebo
    cred = suf[suf["verdict"] == "CREDIBLE (passes placebo)"]
    assert cred["significant"].all()
    assert cred["placebo_sufficient"].all() and (~cred["placebo_significant"]).all()
