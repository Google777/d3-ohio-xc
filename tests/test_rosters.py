"""Tests for roster/origin parsing and the state resolver."""
from d3xc.scrape import rosters

ROSTER_HTML = """
<html><body>
<table>
<tr><th>Full Name</th><th>Yr.</th><th>Hometown / High School</th></tr>
<tr><td><a>Jacob Brechbill</a></td><td>Jr.</td><td>Newark, Ohio / Newark</td></tr>
<tr><td><a>Drew Carpenter</a></td><td>Sr.</td><td>Chesterton, Ind. / Chesterton</td></tr>
<tr><td><a>Cole Clodgo</a></td><td>Sr.</td><td>Raleigh, N.C. / Sanderson</td></tr>
<tr><td><a>William Fontana</a></td><td>So.</td><td>Glenview, IL / Glenbrook South</td></tr>
<tr><td><a>First Year</a></td><td>Fy.</td><td>/</td></tr>
</table>
</body></html>
"""


def test_home_state_code():
    assert rosters.home_state_code("Newark, Ohio") == "OH"
    assert rosters.home_state_code("Chesterton, Ind.") == "IN"
    assert rosters.home_state_code("Raleigh, N.C.") == "NC"
    assert rosters.home_state_code("Glenview, IL") == "IL"
    assert rosters.home_state_code("Piedmont, Calif.") == "CA"
    assert rosters.home_state_code("NoComma") is None


def test_parse_roster():
    recs = rosters.parse_roster(ROSTER_HTML)
    assert len(recs) == 4                      # blank-origin first-year skipped
    by = {r["name"]: r for r in recs}
    assert by["Jacob Brechbill"]["home_state"] == "OH"
    assert by["Jacob Brechbill"]["high_school"] == "Newark"
    assert by["Drew Carpenter"]["hometown"] == "Chesterton, Ind."
    assert by["Drew Carpenter"]["home_state"] == "IN"
    assert by["William Fontana"]["home_state"] == "IL"


def test_roster_url():
    assert rosters.roster_url("https://x.com", "mens-cross-country").endswith(
        "/sports/mens-cross-country/roster")
    assert rosters.roster_url("https://x.com/", "mens-cross-country", 2019).endswith(
        "/sports/mens-cross-country/roster/2019")
