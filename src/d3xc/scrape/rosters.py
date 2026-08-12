"""Parse college roster pages (Sidearm layout) for athlete origin.

Roster tables carry a 'Hometown / High School' column, e.g.
    Drew Carpenter | Sr. | Chesterton, Ind. / Chesterton
from which we derive hometown, home state (2-letter), and high school. This is
the authoritative origin link (it's the athlete's own college roster entry), so
matching to our DB is by name+team+gender.

Historical rosters live at .../roster/<year>; the season dropdown goes back years.
"""
from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

# AP-style / full-name / postal -> 2-letter postal code (all 50 + DC)
_POSTAL = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}
_STATE = {
    "ala": "AL", "alaska": "AK", "ariz": "AZ", "ark": "AR", "calif": "CA",
    "colo": "CO", "conn": "CT", "del": "DE", "fla": "FL", "ga": "GA",
    "hawaii": "HI", "idaho": "ID", "ill": "IL", "ind": "IN", "iowa": "IA",
    "kan": "KS", "kans": "KS", "ky": "KY", "la": "LA", "maine": "ME",
    "md": "MD", "mass": "MA", "mich": "MI", "minn": "MN", "miss": "MS",
    "mo": "MO", "mont": "MT", "neb": "NE", "nebr": "NE", "nev": "NV",
    "nh": "NH", "nj": "NJ", "nm": "NM", "ny": "NY", "nc": "NC", "nd": "ND",
    "ohio": "OH", "okla": "OK", "ore": "OR", "pa": "PA", "ri": "RI",
    "sc": "SC", "sd": "SD", "tenn": "TN", "texas": "TX", "utah": "UT",
    "vt": "VT", "va": "VA", "wash": "WA", "wva": "WV", "wis": "WI",
    "wisc": "WI", "wyo": "WY", "dc": "DC",
}
_FULL = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "newhampshire": "NH", "newjersey": "NJ", "newmexico": "NM", "newyork": "NY",
    "northcarolina": "NC", "northdakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhodeisland": "RI",
    "southcarolina": "SC", "southdakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "westvirginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


def home_state_code(hometown: str) -> Optional[str]:
    """Extract a 2-letter state code from a 'City, State' hometown string."""
    if not hometown or "," not in hometown:
        return None
    tail = hometown.rsplit(",", 1)[1].strip()
    up = tail.upper().replace(".", "").replace(" ", "")
    if up in _POSTAL:
        return up
    key = tail.lower().replace(".", "").replace(" ", "")
    return _STATE.get(key) or _FULL.get(key)


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def parse_roster(html: str, default_state: str = "OH") -> list[dict]:
    """Return [{name, class_year, hometown, home_state, high_school}] from a
    Sidearm roster page's data table.

    Convention: many Ohio rosters list in-state athletes with just the city
    ('Akron') and only add a state for out-of-state athletes ('Hamburg, N.Y.').
    Since every tracked school is in Ohio, a comma-less hometown is treated as
    `default_state` (OH).
    """
    soup = BeautifulSoup(html, "lxml")
    out = []
    for table in soup.find_all("table"):
        hdr = [_clean(th.get_text()).lower() for th in table.find_all("th")]
        if not any("hometown" in h for h in hdr) or not any("name" in h for h in hdr):
            continue
        name_i = next(i for i, h in enumerate(hdr) if "name" in h)
        home_i = next(i for i, h in enumerate(hdr) if "hometown" in h)
        yr_i = next((i for i, h in enumerate(hdr) if h.startswith("yr") or "class" in h), None)
        # separate 'High School' column (Kenyon-style) vs combined cell (Denison)
        combined = "high school" in hdr[home_i]
        hs_i = None if combined else next(
            (i for i, h in enumerate(hdr) if h.strip() == "high school"), None)
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) <= home_i:
                continue
            name = _clean(tds[name_i].get_text())
            home_cell = _clean(tds[home_i].get_text())
            if not name:
                continue
            if "/" in home_cell:                       # 'City, ST / High School'
                hometown, hs = [p.strip() for p in home_cell.split("/", 1)]
            else:                                       # separate columns
                hometown = home_cell
                hs = _clean(tds[hs_i].get_text()) if hs_i is not None and hs_i < len(tds) else None
            if not hometown:
                continue
            state = home_state_code(hometown)
            if state is None and "," not in hometown:
                state = default_state          # in-state athlete listed as city only
            out.append({
                "name": name,
                "class_year": _clean(tds[yr_i].get_text()) if yr_i is not None and yr_i < len(tds) else None,
                "hometown": hometown,
                "home_state": state,
                "high_school": hs or None,
            })
        if out:
            break
    return out


def roster_url(base: str, sport_path: str, year: Optional[int] = None) -> str:
    """Build a roster URL; year=None -> current roster."""
    url = f"{base.rstrip('/')}/sports/{sport_path}/roster"
    return f"{url}/{year}" if year else url
