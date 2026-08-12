from d3xc.scrape import tfrrs

TEAM_HTML = """
<html><body>
<table><tbody>
<tr><td><a href="/athletes/1001/Mount_Union/Alex_Miller.html">Alex Miller</a></td><td>JR</td></tr>
<tr><td><a href="/athletes/1002/Mount_Union/Jordan_Davis.html">Jordan Davis</a></td><td>FR</td></tr>
<tr><td><a href="/athletes/1001/Mount_Union/Alex_Miller.html">Alex Miller</a></td><td>JR</td></tr>
</tbody></table>
</body></html>
"""

ATHLETE_HTML = """
<html><body>
<h3>Alex Miller</h3>
<a href="/athletes/1001/Mount_Union/Alex_Miller.html">profile</a>
<table><tbody>
<tr><td>2023-10-15</td><td>All-Ohio Championships</td><td>24:33.4</td><td>12</td></tr>
<tr><td>2022-09-30</td><td>Early Season Open</td><td>25:10.0</td><td>34</td></tr>
<tr><td>header</td><td>no time here</td><td>--</td></tr>
</tbody></table>
</body></html>
"""


def test_team_url():
    assert tfrrs.team_url("OH_college_Mount_Union", "men").endswith(
        "/teams/xc/OH_college_m_Mount_Union.html"
    )
    assert tfrrs.team_url("OH_college_Mount_Union", "women").endswith(
        "/teams/xc/OH_college_f_Mount_Union.html"
    )


def test_parse_roster_dedup_and_class():
    roster = tfrrs.parse_team_roster(TEAM_HTML, "Mount Union", "men", 2023)
    names = [r.athlete_name for r in roster]
    assert names == ["Alex Miller", "Jordan Davis"]  # deduped
    assert roster[0].tfrrs_athlete_id == "1001"
    assert roster[0].class_year == "JR"


def test_parse_athlete_results():
    res = tfrrs.parse_athlete_results(ATHLETE_HTML, "Mount Union", "men",
                                      only_seasons=[2022, 2023])
    seasons = sorted(r.season for r in res)
    assert seasons == [2022, 2023]
    r2023 = next(r for r in res if r.season == 2023)
    assert abs(r2023.mark_seconds - (24 * 60 + 33.4)) < 1e-6
    assert "All-Ohio" in r2023.meet_name
    assert r2023.distance_m == 8000  # men std


def test_normalize_distance():
    assert tfrrs.normalize_distance("8k") == 8000
    assert tfrrs.normalize_distance("8,000m") == 8000
    assert tfrrs.normalize_distance("6000") == 6000
    assert tfrrs.normalize_distance("5 mi") == 8047
    assert tfrrs.normalize_distance("3.11M") == 5005   # XC mile course -> ~5k
    assert tfrrs.normalize_distance("6k") == 6000


def test_is_xc_event():
    assert tfrrs.is_xc_event("8k")
    assert tfrrs.is_xc_event("6k")
    assert tfrrs.is_xc_event("3.11M")
    assert tfrrs.is_xc_event("8000m (XC)")
    # track events are NOT cross country
    assert not tfrrs.is_xc_event("1500")
    assert not tfrrs.is_xc_event("5000")
    assert not tfrrs.is_xc_event("Mile")
    assert not tfrrs.is_xc_event("DMR")


# mirrors real TFRRS athlete-page structure: flat meet tables with a dated
# header <th>, rows of (event, time, place); track + XC interleaved.
REAL_XC_HTML = """
<html><body>
<h3>LIAM BLAKE (SR-4)</h3>
<a href="/athletes/8594171/Mount_Union/Liam_Blake.html">x</a>
<table><tr><th>OAC Outdoor Championships May 1- 2, 2025</th></tr>
<tr><td>1500</td><td>3:58.86</td><td>6th (F)</td></tr></table>
<table><tr><th>Ohio Athletic Conference XC Championships Nov 1, 2024</th></tr>
<tr><td>8k</td><td>25:34.1</td><td>19th</td></tr></table>
<table><tr><th>Tommy Evans Cross Country Invitational Sep 2, 2023</th></tr>
<tr><td>6k</td><td>20:02.6</td><td>97th</td></tr></table>
</body></html>
"""


def test_parse_athlete_xc_real_structure():
    res = tfrrs.parse_athlete_xc(REAL_XC_HTML, "Mount Union", "men")
    # only the two XC rows, not the 1500 track race
    assert len(res) == 2
    by_season = {r.season: r for r in res}
    assert set(by_season) == {2024, 2023}
    r24 = by_season[2024]
    assert r24.distance_m == 8000
    assert abs(r24.mark_seconds - (25 * 60 + 34.1)) < 1e-6
    assert r24.place_overall == 19
    assert "Conference XC" in r24.meet_name
    assert by_season[2023].distance_m == 6000


def test_parse_athlete_xc_ignores_course_record_year():
    html = """
    <html><body><h3>A B</h3>
    <table><tr><th>NCAA Great Lakes Regional Nov 11, 2023 (course record 2006)</th></tr>
    <tr><td>8k</td><td>26:07.8</td><td>48th</td></tr></table></body></html>
    """
    res = tfrrs.parse_athlete_xc(html, "Mount Union", "men")
    assert len(res) == 1
    assert res[0].season == 2023   # date year, not the 2006 course-record note
