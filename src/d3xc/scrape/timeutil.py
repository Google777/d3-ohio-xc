"""Time parsing/formatting shared across scrape and analyze layers."""
from __future__ import annotations

import re
from typing import Optional

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_DATE_RE = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})"
    r"(?:\s*-\s*(?:[a-z]*\.?\s*)?\d{1,2})?,?\s*(20\d\d)", re.I
)


def parse_meet_date(text: str) -> Optional[int]:
    """Parse a meet date like 'October 28, 2023' or 'May 7- 8, 2026' into a
    sortable integer YYYYMMDD (first day of a range). Returns None if unparseable."""
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower()[:3])
    day = int(m.group(2))
    year = int(m.group(3))
    if not month:
        return None
    return year * 10000 + month * 100 + day

_TIME_RE = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)\s*$")
_MMSS_RE = re.compile(r"^\s*(\d{1,3}):(\d{2}(?:\.\d+)?)\s*$")


def time_to_seconds(text: str) -> Optional[float]:
    """Parse 'H:MM:SS.s', 'MM:SS.s', or 'SS.s' into seconds.

    Returns None if the text is not a recognizable time.
    """
    if text is None:
        return None
    t = text.strip()
    if not t or t in {"-", "--", "DNF", "DNS", "DQ", "NT"}:
        return None
    m = _TIME_RE.match(t)
    if m:
        hours = int(m.group(1)) if m.group(1) else 0
        minutes = int(m.group(2))
        seconds = float(m.group(3))
        return hours * 3600 + minutes * 60 + seconds
    m = _MMSS_RE.match(t)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    # NOTE: no bare-number fallback. On TFRRS, event labels like "800" or "5000"
    # are distances, not times; treating them as seconds corrupts results.
    return None


def riegel_project(t_seconds, from_m, to_m, exp: float = 1.06):
    """Fatigue-adjusted race-time projection across distances (Riegel):
        t2 = t1 * (d2/d1) ** exp
    Unlike linear pace (exp=1), this correctly makes an 8k *slower per km* than
    a 5k. exp~1.06 is the standard distance-running value.
    """
    if not t_seconds or not from_m or not to_m or from_m <= 0:
        return None
    return float(t_seconds) * (to_m / from_m) ** exp


def seconds_to_time(seconds: Optional[float]) -> str:
    """Format seconds as 'MM:SS.s' (or 'H:MM:SS.s' when >= 1 hour)."""
    if seconds is None:
        return ""
    seconds = float(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours >= 1:
        return f"{int(hours)}:{int(minutes):02d}:{secs:04.1f}"
    return f"{int(minutes)}:{secs:04.1f}"
