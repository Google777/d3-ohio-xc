"""Tests for the TFRRS meet-results scraper."""
from d3xc.scrape import tfrrs

MEET_HTML = """
<html><head><title>TFRRS | OAC XC Championships - Meet Results</title></head>
<body>
<h1>Ohio Athletic Conference XC Championships</h1>
<p>October 28, 2023 | Hosted by Otterbein</p>

<h3>8K Men Team Results (8k)</h3>
<table>
<tr><th>PL</th><th>Team</th><th>Total Time</th><th>Avg. Time</th><th>Score</th></tr>
<tr><td>1</td><td>John Carroll</td><td>2:03:40</td><td>24:44</td><td>25</td></tr>
<tr><td>2</td><td>Mount Union</td><td>2:04:10</td><td>24:50</td><td>60</td></tr>
<tr><td>3</td><td>Wilmington (Ohio)</td><td>2:05:00</td><td>25:00</td><td>78</td></tr>
</table>

<h3>8K Men Individual Results (8k)</h3>
<table>
<tr><th>PL</th><th>NAME</th><th>YEAR</th><th>TEAM</th><th>Avg. Mile</th><th>TIME</th><th>SCORE</th></tr>
<tr><td>1</td><td>Simon Heys</td><td>SR-4</td><td>Wilmington (Ohio)</td><td>4:52.8</td><td>24:15.8</td><td>1</td></tr>
<tr><td>2</td><td>Liam Blake</td><td>SO-2</td><td>Mount Union</td><td>4:55.0</td><td>24:26.0</td><td>2</td></tr>
<tr><td>3</td><td>Random Runner</td><td>FR-1</td><td>Notre Dame College</td><td>4:56.0</td><td>24:30.0</td><td>3</td></tr>
</table>
</body></html>
"""


def test_classify_meet_kind():
    assert tfrrs.classify_meet_kind("Ohio Athletic Conference XC Championships") == "conference"
    assert tfrrs.classify_meet_kind("2024 NCAC Cross Country Championships") == "conference"
    assert tfrrs.classify_meet_kind(
        "NCAA Division III Great Lakes Region Cross Country Championships") == "regional"
    assert tfrrs.classify_meet_kind("NCAA Division III Cross Country Championships") == "national"
    assert tfrrs.classify_meet_kind("Otterbein XC Invite") == "invitational"
    # validated edge cases: previews/pre-nationals are invites, not the national;
    # a non-NCAA 'inter-regional' invite is not the NCAA regional championship.
    assert tfrrs.classify_meet_kind("2022 DIII National Preview") == "invitational"
    assert tfrrs.classify_meet_kind("NCAA DIII Pre-Nationals") == "invitational"
    assert tfrrs.classify_meet_kind("KollegeTown Pre National Meet") == "invitational"
    assert tfrrs.classify_meet_kind("Oberlin College Inter-Regional Rumble") == "invitational"
    # a conference 'Preview' is an invite, not the conference championship
    assert tfrrs.classify_meet_kind("NCAC Preview Meet") == "invitational"
    assert tfrrs.classify_meet_kind("North Coast Athletic Conference Championships") == "conference"


def test_normalize_team_name():
    assert tfrrs.normalize_team_name("Wilmington (Ohio)") == "Wilmington"
    assert tfrrs.normalize_team_name("Mount Union") == "Mount Union"
    assert tfrrs.normalize_team_name("Mt. Union") == "Mount Union"
    assert tfrrs.normalize_team_name("Case Western Reserve (OH)") == "Case Western Reserve"


def test_discover_meet_links():
    html = ('<a href="/results/xc/21925/Ohio_Athletic_Conference_XC_Championships">x</a>'
            '<a href="/results/xc/21925/Ohio_Athletic_Conference_XC_Championships">dup</a>'
            '<a href="/results/95769/OAC_Outdoor">track-not-xc</a>'
            '<a href="/results/21925/5510346">individual-perf</a>'
            '<a href="/results/xc/22997/Great_Lakes_Region">y</a>')
    links = tfrrs.discover_meet_links(html)
    assert len(links) == 2                       # deduped, xc-only
    assert any("21925" in u for u in links)
    assert any("22997" in u for u in links)
    assert all("/results/xc/" in u and u.endswith(".html") for u in links)


def test_parse_meet_teams_and_individuals():
    m = tfrrs.parse_meet(MEET_HTML)
    assert m["season"] == 2023
    assert m["meet_kind"] == "conference"
    # team placements
    tp = {p.team: p for p in m["team_placements"]}
    assert tp["John Carroll"].team_place == 1 and tp["John Carroll"].team_points == 25
    assert tp["Wilmington"].team_place == 3        # normalized from 'Wilmington (Ohio)'
    assert all(p.gender == "men" for p in m["team_placements"])
    # individuals: distance from '8K' heading, time parsed, normalized team
    ind = {r.athlete_name: r for r in m["individual_results"]}
    assert ind["Simon Heys"].team == "Wilmington"
    assert ind["Simon Heys"].distance_m == 8000
    assert abs(ind["Simon Heys"].mark_seconds - (24 * 60 + 15.8)) < 1e-6
    assert ind["Liam Blake"].place_overall == 2


def test_parse_meet_known_teams_filter():
    m = tfrrs.parse_meet(MEET_HTML, known_teams={"Mount Union"})
    teams = {p.team for p in m["team_placements"]}
    assert teams == {"Mount Union"}               # John Carroll / Wilmington filtered out
    assert all(r.team == "Mount Union" for r in m["individual_results"])


# some meets label gender as "(M)"/"(W)" instead of "Men"/"Women"
PARENS_GENDER_HTML = """
<html><head><title>NCAA DIII XC Championships - Meet Results</title></head><body>
<h1>NCAA Division III Cross Country Championships</h1>
<p>November 18, 2017</p>
<h3>(M) 8k R. CC Team Results (8k)</h3>
<table><tr><th>PL</th><th>Team</th><th>Score</th></tr>
<tr><td>19</td><td>Ohio Northern</td><td>456</td></tr>
<tr><td>29</td><td>Otterbein</td><td>601</td></tr></table>
<h3>(W) 6k R. CC Team Results (6k)</h3>
<table><tr><th>PL</th><th>Team</th><th>Score</th></tr>
<tr><td>25</td><td>Case Western (Ohio)</td><td>580</td></tr></table>
</body></html>
"""


def test_parse_meet_parenthetical_gender():
    m = tfrrs.parse_meet(PARENS_GENDER_HTML)
    assert m["season"] == 2017 and m["meet_kind"] == "national"
    by = {(p.team, p.gender): p.team_place for p in m["team_placements"]}
    assert by[("Ohio Northern", "men")] == 19        # "(M)" -> men
    assert by[("Otterbein", "men")] == 29
    assert by[("Case Western Reserve", "women")] == 25  # "(W)" -> women, normalized
    assert all(p.gender for p in m["team_placements"])   # no empty genders
