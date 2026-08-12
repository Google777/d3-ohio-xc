"""Tests for VDOT standardization + calibrated course adjustment."""
import pytest

from d3xc import config
from d3xc.analyze import standardize as SZ


def test_vdot_known_values_and_distance_normalization():
    # a 5k in 15:00 is ~VDOT 69-70; VDOT should be roughly distance-invariant:
    # an equivalent ~24:50 8k should land close (within a few points).
    v5 = SZ.vdot_from_time(900, 5000)
    assert 66 <= v5 <= 72
    v8 = SZ.vdot_from_time(24 * 60 + 50, 8000)
    assert abs(v8 - v5) < 6                      # distance handled, not identical


def test_vdot_to_time_inverse():
    for d in (5000, 6000, 8000):
        t = SZ.vdot_to_time(62.0, d)
        assert abs(SZ.vdot_from_time(t, d) - 62.0) < 0.2


@pytest.mark.skipif(not config.DB_PATH.exists(), reason="no DB")
def test_course_adjustment_and_calibration_coherent():
    from d3xc.analyze.metrics import load_frames
    f = load_frames()
    adf = SZ.course_adjusted_performances(f["results"])   # championship-anchored
    assert {"vdot", "adj_vdot", "meet_key"}.issubset(adf.columns)
    # only tracked teams by default
    if "tracked" in adf.columns:
        assert adf["tracked"].all()
    tl = SZ.vdot_tier_summary(f)
    # coherence: OAC winning bar >= NCAC winning bar (men)
    men = tl[tl.gender == "men"].set_index("tier")["median_vdot"]
    if {"Win OAC", "Win NCAC"}.issubset(men.index):
        # RELATIVE coherence is what's trustworthy: OAC is the tougher bar.
        assert men["Win OAC"] >= men["Win NCAC"] - 0.5
        # absolute scale is only sanity-bounded (calibration is approximate)
        assert 50 <= men["Win OAC"] <= 75
