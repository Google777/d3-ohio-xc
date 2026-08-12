"""TFRRS parsers for team, athlete, and meet pages.

IMPORTANT: TFRRS markup is not a stable public API. The selectors here target
TFRRS's conventional layout (Bootstrap-style tables inside panels), but they are
written defensively and may need adjustment against live HTML. Every parser is a
*pure function* of HTML text so it can be unit-tested against saved fixtures
without network access. Orchestration (which URLs to hit) is separated from
parsing so the two can evolve independently.

URL conventions (observed):
    Team page:    {BASE}/teams/xc/{slug}_{g}.html            g in {m,f}
    Athlete page: {BASE}/athletes/{id}/{...}.html
    Meet page:    {BASE}/results/{id}/{...}.html
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

from bs4 import BeautifulSoup

from d3xc import config
from d3xc.scrape.records import MeetTeamPlacement, RaceResult, RosterEntry
from d3xc.scrape.timeutil import time_to_seconds

log = logging.getLogger(__name__)

_GENDER_CODE = {"men": "m", "women": "f"}
_ATHLETE_ID_RE = re.compile(r"/athletes/(\d+)")
# NOTE: longer/more-specific units must precede 'm'/'k' in the alternation,
# otherwise 'mi' would match as 'm' + leftover 'i'.
_DIST_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(km|mi|miles?|meters?|k|m)?", re.I)


# --------------------------------------------------------------------------
# URL builders
# --------------------------------------------------------------------------
def team_url(slug: str, gender: str, base: str = config.TFRRS_BASE) -> str:
    """Build a TFRRS XC team URL.

    Real TFRRS slugs are ``STATE_college_GENDER_Name`` (gender in the middle),
    e.g. ``OH_college_m_Mount_Union``. Config stores the gender-less form
    ``OH_college_Mount_Union``; we insert the gender code after ``college_``.
    """
    g = _GENDER_CODE[gender]
    full = slug.replace("_college_", f"_college_{g}_", 1)
    return f"{base}/teams/xc/{full}.html"


def athlete_url(athlete_id: str, base: str = config.TFRRS_BASE) -> str:
    return f"{base}/athletes/{athlete_id}.html"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def normalize_distance(text: str) -> Optional[int]:
    """Turn '8k', '8,000m', '6000', '5 mile' into meters (best-effort)."""
    if not text:
        return None
    t = text.strip().lower()
    m = _DIST_RE.search(t.replace(",", ""))
    if not m:
        return None
    value = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit in {"k", "km"}:
        return int(value * 1000)
    if unit in {"mi", "mile", "miles"}:
        return int(round(value * 1609.34))
    # In XC context, a small value tagged 'm' (e.g. '3.11M') means miles, not
    # meters (no race is < 50 m). Larger values are genuine meters.
    if unit == "m" and value < 50:
        return int(round(value * 1609.34))
    return int(value)


def _athlete_id_from_href(href: str) -> Optional[str]:
    if not href:
        return None
    m = _ATHLETE_ID_RE.search(href)
    return m.group(1) if m else None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# --------------------------------------------------------------------------
# parsers (pure functions of HTML)
# --------------------------------------------------------------------------
def parse_team_roster(html: str, team: str, gender: str, season: int) -> list[RosterEntry]:
    """Extract the roster (athlete name/id/class) from a TFRRS team page.

    Looks for anchors linking to /athletes/{id}. Class year is pulled from a
    sibling cell when present. Deduplicates by athlete id/name.
    """
    soup = _soup(html)
    seen: set[str] = set()
    out: list[RosterEntry] = []
    for a in soup.select("a[href*='/athletes/']"):
        name = _clean(a.get_text())
        if not name:
            continue
        aid = _athlete_id_from_href(a.get("href", ""))
        key = aid or name.lower()
        if key in seen:
            continue
        seen.add(key)

        class_year = None
        row = a.find_parent("tr")
        if row:
            cells = [_clean(td.get_text()) for td in row.find_all("td")]
            for c in cells:
                if c.upper() in {"FR", "SO", "JR", "SR", "RS", "FR-1", "SR-4"}:
                    class_year = c.upper()
                    break
        out.append(
            RosterEntry(
                team=team,
                gender=gender,
                season=season,
                athlete_name=name,
                tfrrs_athlete_id=aid,
                class_year=class_year,
            )
        )
    return out


def parse_athlete_results(
    html: str,
    team: str,
    gender: str,
    only_seasons: Optional[Iterable[int]] = None,
) -> list[RaceResult]:
    """Extract XC race results from an athlete page.

    Scans result tables for rows containing a time-like mark and a meet name.
    Season/year is inferred from a date column when available.
    """
    soup = _soup(html)
    name_el = soup.select_one("h3, h2, .panel-heading")
    athlete_name = _clean(name_el.get_text()) if name_el else ""
    aid = None
    canonical = soup.select_one("a[href*='/athletes/']")
    if canonical:
        aid = _athlete_id_from_href(canonical.get("href", ""))

    season_filter = set(only_seasons) if only_seasons else None
    out: list[RaceResult] = []
    for tr in soup.select("tr"):
        cells = [_clean(td.get_text()) for td in tr.find_all("td")]
        if len(cells) < 2:
            continue
        mark_seconds = None
        mark_idx = None
        for i, c in enumerate(cells):
            secs = time_to_seconds(c)
            if secs is not None:
                mark_seconds, mark_idx = secs, i
                break
        if mark_seconds is None:
            continue
        text_cells = [c for j, c in enumerate(cells) if j != mark_idx and c]
        meet_name = max(text_cells, key=len) if text_cells else ""
        year = _infer_year(cells)
        if season_filter and year not in season_filter:
            continue
        out.append(
            RaceResult(
                team=team,
                gender=gender,
                season=year or 0,
                athlete_name=athlete_name,
                tfrrs_athlete_id=aid,
                meet_name=meet_name,
                meet_date=None,
                distance_m=config.XC_DISTANCES_M.get(gender),
                mark_seconds=mark_seconds,
            )
        )
    return out


_YEAR_RE = re.compile(r"(20\d{2})")
_MONTH_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", re.I
)
_SECTION_RE = re.compile(r"(20\d\d)\s*(XC|Indoor|Outdoor)", re.I)
_COLON_TIME = re.compile(r"^\s*(?:\d+:)?\d{1,2}:\d{2}(?:\.\d+)?\s*$")
_PLACE_RE = re.compile(r"^\s*(\d{1,3})(?:st|nd|rd|th)?\b")


def _infer_year(cells: list[str]) -> Optional[int]:
    for c in cells:
        m = _YEAR_RE.search(c)
        if m:
            return int(m.group(1))
    return None


def _split_meet_header(text: str) -> tuple[str, Optional[str]]:
    """Split 'Meet Name ... May 7- 8, 2026' into (name, iso-ish date str)."""
    mo = _MONTH_RE.search(text)
    if mo:
        name = text[: mo.start()].strip(" -,\u00a0")
        date = text[mo.start():].strip()
        return (name or text, date)
    return (text, None)


_DATE_YEAR_RE = re.compile(
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}"
    r"(?:\s*-\s*[A-Za-z]*\.?\s*\d{1,2})?,?\s*(20\d\d)", re.I
)


def _year_from_header(htext: str) -> Optional[int]:
    """Year belonging to the meet *date* (not stray years like course records)."""
    m = _DATE_YEAR_RE.search(htext)
    if m:
        return int(m.group(1))
    years = _YEAR_RE.findall(htext)
    return int(years[-1]) if years else None


_XC_EVENT_RE = re.compile(r"^\s*\d+(?:\.\d+)?\s*[km]\s*$", re.I)


def is_xc_event(event: str) -> bool:
    """True if an event label denotes a cross-country race (not track)."""
    e = (event or "").strip().lower()
    if not e:
        return False
    if "xc" in e:
        return True
    # '8k','6k','5k' (XC uses lowercase k) or '3.11m'/'5m' (mile courses).
    # Track distances render as '1500','5000','Mile','DMR' and are excluded.
    return bool(_XC_EVENT_RE.match(e))


def parse_athlete_xc(
    html: str, team: str, gender: str,
    only_seasons: Optional[Iterable[int]] = None,
) -> list[RaceResult]:
    """Parse cross-country results from a real TFRRS athlete page.

    Results are a flat, reverse-chronological list of meet tables; each table's
    header holds the meet name + date (with the year). We read the year from the
    header and classify each row as XC via its event token (``is_xc_event``),
    using colon-formatted times so event-distance labels are never misread.
    """
    soup = _soup(html)
    name_el = soup.find(["h1", "h2", "h3"])
    athlete_name = _clean(name_el.get_text()) if name_el else ""
    athlete_name = re.sub(r"\(.*?\)", "", athlete_name).strip()
    aid = None
    canonical = soup.select_one("a[href*='/athletes/']")
    if canonical:
        aid = _athlete_id_from_href(canonical.get("href", ""))

    season_filter = set(only_seasons) if only_seasons else None
    out: list[RaceResult] = []

    for table in soup.find_all("table"):
        th = table.find("th")
        if not th:
            continue
        htext = _clean(th.get_text())
        season = _year_from_header(htext)
        if season is None or not _MONTH_RE.search(htext):
            continue  # not a dated meet table
        if season_filter and season not in season_filter:
            continue
        meet_name, meet_date = _split_meet_header(htext)

        for tr in table.find_all("tr"):
            cells = [_clean(td.get_text()) for td in tr.find_all("td")]
            if len(cells) < 2 or not is_xc_event(cells[0]):
                continue
            event = cells[0]
            mark = None
            for c in cells[1:]:
                if _COLON_TIME.match(c):
                    mark = time_to_seconds(c)
                    break
            if mark is None:
                continue
            place = None
            for c in cells[1:]:
                if not _COLON_TIME.match(c):
                    pm = _PLACE_RE.match(c)
                    if pm:
                        place = int(pm.group(1))
                        break
            out.append(RaceResult(
                team=team, gender=gender, season=season,
                athlete_name=athlete_name, tfrrs_athlete_id=aid,
                meet_name=meet_name, meet_date=meet_date,
                distance_m=normalize_distance(event) or config.XC_DISTANCES_M.get(gender),
                mark_seconds=mark, place_overall=place,
            ))
    return out


def discover_athlete_links(html: str) -> list[tuple[str, str]]:
    """Return (athlete_id, name) pairs linked from a page."""
    soup = _soup(html)
    out = []
    seen = set()
    for a in soup.select("a[href*='/athletes/']"):
        aid = _athlete_id_from_href(a.get("href", ""))
        name = _clean(a.get_text())
        if aid and aid not in seen:
            seen.add(aid)
            out.append((aid, name))
    return out


# --------------------------------------------------------------------------
# meet results
# --------------------------------------------------------------------------
_MEET_LINK_RE = re.compile(r"/results/xc/(\d+)/([A-Za-z0-9_%\-]+)")
_HEADING_DIST_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([kmKM])")
_FULL_DATE_RE = re.compile(
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+(20\d\d)"
)


def meet_result_url(meet_id: str | int, slug: str = "meet",
                    base: str = config.TFRRS_BASE) -> str:
    return f"{base}/results/xc/{meet_id}/{slug}.html"


def discover_meet_links(html: str, base: str = config.TFRRS_BASE) -> list[str]:
    """Return absolute XC meet-result URLs linked from a page (deduped).

    Matches only meet pages (``/results/xc/{id}/{Name}``), not individual
    performance links (``/results/{meet}/{result_id}``).
    """
    out, seen = [], set()
    for m in _MEET_LINK_RE.finditer(html):
        mid = m.group(1)
        if mid in seen:
            continue
        seen.add(mid)
        out.append(f"{base}/results/xc/{mid}/{m.group(2)}.html")
    return out


def classify_meet_kind(name: str) -> str:
    """Classify a meet by name into national/regional/conference/invitational.

    Validated against authoritative results (e.g. 2022 Denison = 15th at the real
    Great Lakes regional; the 'DIII National Preview' is an in-season invite).
    Only genuine NCAA championship meets count:
      * regional  = NCAA regional championship ('ncaa' + 'region')
      * national  = NCAA DIII national championship ('ncaa' + 'championship',
                    no 'region', and NOT a preview / pre-national invite)
    So 'Oberlin Inter-Regional Rumble' (no 'ncaa') and 'DIII National Preview' /
    'Pre-Nationals' (previews) correctly fall through to invitational.
    """
    n = (name or "").lower()
    # Previews / pre-nationals are in-season invitationals, never championships.
    if any(k in n for k in ("pre-nat", "pre nat", "prenational",
                            "pre-national", "preview")):
        return "invitational"
    if "ncaa" in n and "region" in n:
        return "regional"
    if ("ncaa" in n and "championship" in n
            and ("division iii" in n or "diii" in n or "d3" in n)):
        return "national"
    conf_markers = [
        "ohio athletic conference", "oac championship", "oac xc",
        "north coast", "ncac", "heartland", "hcac",
        "university athletic association", "uaa",
        "conference championship",
    ]
    if any(k in n for k in conf_markers):
        return "conference"
    return "invitational"


# TFRRS often qualifies duplicate school names with a state; strip that and map
# a few known aliases back to our canonical config names.
_STATE_QUAL_RE = re.compile(r"\s*\((?:oh|ohio|o\.)\)\s*$", re.I)
_TEAM_ALIASES = {
    "mt. union": "Mount Union",
    "mount st. joseph": "Mount St. Joseph",
    "mt. st. joseph": "Mount St. Joseph",
    "case western": "Case Western Reserve",
}


def normalize_team_name(name: str) -> str:
    """Normalize a TFRRS team label to our canonical form ('Wilmington (Ohio)'->'Wilmington')."""
    n = _STATE_QUAL_RE.sub("", _clean(name)).strip()
    return _TEAM_ALIASES.get(n.lower(), n)


def _header_index(table) -> dict:
    """Map lowercased header labels -> column index for a results table."""
    ths = table.find_all("th")
    return {_clean(th.get_text()).lower(): i for i, th in enumerate(ths)}


def _heading_gender_distance(heading: str) -> tuple[Optional[str], Optional[int]]:
    h = heading.lower()
    # gender markers vary by year: 'Men'/'Women', "Men's", or "(M)"/"(W)".
    # check women first ('men' is a substring of 'women').
    if "women" in h or "(w)" in h or "girls" in h:
        gender = "women"
    elif "men" in h or "(m)" in h or "boys" in h:
        gender = "men"
    else:
        gender = None
    dm = _HEADING_DIST_RE.search(heading)
    dist = normalize_distance(f"{dm.group(1)}{dm.group(2)}") if dm else None
    # fallback: championship XC distances are gendered (men 8k, women 6k)
    if gender is None and dist is not None:
        if dist == 8000:
            gender = "men"
        elif dist == 6000:
            gender = "women"
    return gender, dist


def parse_meet(html: str, known_teams: Optional[set[str]] = None) -> dict:
    """Parse a TFRRS XC meet-results page.

    Returns a dict with meet_name, meet_date, season, meet_kind,
    team_placements (list[MeetTeamPlacement]) and individual_results
    (list[RaceResult]). If ``known_teams`` is given, rows are filtered to those
    teams (after normalization).
    """
    soup = _soup(html)
    title = soup.find(["h1", "h2", "h3"])
    meet_name = _clean(title.get_text()) if title else ""
    meet_name = re.sub(r"\s*-\s*Meet Results.*$", "", meet_name)
    page_text = soup.get_text(" ", strip=True)
    dm = _FULL_DATE_RE.search(page_text)
    season = int(dm.group(1)) if dm else None
    meet_date = dm.group(0) if dm else None
    kind = classify_meet_kind(meet_name)

    placements: list[MeetTeamPlacement] = []
    individuals: list[RaceResult] = []

    for table in soup.find_all("table"):
        prev = table.find_previous(["h1", "h2", "h3", "h4"])
        heading = _clean(prev.get_text()) if prev else ""
        hl = heading.lower()
        gender, dist = _heading_gender_distance(heading)
        idx = _header_index(table)

        if "team results" in hl:
            pl_i = idx.get("pl", 0)
            team_i = idx.get("team", 1)
            score_i = idx.get("score")
            for tr in table.find_all("tr")[1:]:
                cells = [_clean(td.get_text()) for td in tr.find_all("td")]
                if len(cells) <= team_i:
                    continue
                team = normalize_team_name(cells[team_i])
                if known_teams is not None and team not in known_teams:
                    continue
                place = _to_int(cells[pl_i]) if pl_i < len(cells) else None
                points = _to_int(cells[score_i]) if score_i is not None and score_i < len(cells) else None
                placements.append(MeetTeamPlacement(
                    meet_name=meet_name, meet_date=meet_date, season=season or 0,
                    gender=gender or "", team=team, team_place=place,
                    team_points=points, meet_kind=kind,
                ))

        elif "individual results" in hl:
            pl_i = idx.get("pl", 0)
            name_i = idx.get("name", 1)
            team_i = idx.get("team", 3)
            time_i = idx.get("time")
            for tr in table.find_all("tr")[1:]:
                cells = [_clean(td.get_text()) for td in tr.find_all("td")]
                if time_i is None or len(cells) <= max(name_i, team_i, time_i):
                    continue
                team = normalize_team_name(cells[team_i])
                if known_teams is not None and team not in known_teams:
                    continue
                mark = time_to_seconds(cells[time_i])
                if mark is None:
                    continue
                individuals.append(RaceResult(
                    team=team, gender=gender or "", season=season or 0,
                    athlete_name=cells[name_i], tfrrs_athlete_id=None,
                    meet_name=meet_name, meet_date=meet_date,
                    distance_m=dist or config.XC_DISTANCES_M.get(gender or ""),
                    mark_seconds=mark, place_overall=_to_int(cells[pl_i]),
                ))

    return {
        "meet_name": meet_name, "meet_date": meet_date, "season": season,
        "meet_kind": kind, "team_placements": placements,
        "individual_results": individuals,
    }


def _to_int(text: str) -> Optional[int]:
    m = re.match(r"\s*(\d+)", text or "")
    return int(m.group(1)) if m else None


def discover_team_athletes(html: str, known_teams: set[str]) -> dict[str, str]:
    """From a meet page, return {athlete_id: team} for rows on tracked teams.

    Used by the backward crawl to follow only our Ohio D3 program lineages (so
    the graph walk stays bounded to Ohio D3 instead of all of national D3).
    """
    soup = _soup(html)
    out: dict[str, str] = {}
    for t in soup.find_all("table"):
        hdr = [_clean(th.get_text()).lower() for th in t.find_all("th")]
        if "name" not in hdr or "team" not in hdr:
            continue
        name_i, team_i = hdr.index("name"), hdr.index("team")
        for tr in t.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) <= max(name_i, team_i):
                continue
            team = normalize_team_name(tds[team_i].get_text())
            if team not in known_teams:
                continue
            a = tds[name_i].find("a", href=True)
            if a:
                aid = _athlete_id_from_href(a["href"])
                if aid:
                    out.setdefault(aid, team)
    return out
