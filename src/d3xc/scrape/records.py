"""Structured records emitted by the scrape layer and consumed by the store."""
from __future__ import annotations

import dataclasses
from typing import Optional


@dataclasses.dataclass
class RosterEntry:
    team: str
    gender: str            # "men" | "women"
    season: int            # XC year, e.g. 2023
    athlete_name: str
    tfrrs_athlete_id: Optional[str] = None
    class_year: Optional[str] = None   # FR/SO/JR/SR/RS


@dataclasses.dataclass
class RaceResult:
    team: str
    gender: str
    season: int
    athlete_name: str
    tfrrs_athlete_id: Optional[str]
    meet_name: str
    meet_date: Optional[str]           # ISO date string if known
    distance_m: Optional[int]          # 8000 / 6000 / 5000 ...
    mark_seconds: Optional[float]      # finish time in seconds
    place_overall: Optional[int] = None


@dataclasses.dataclass
class MeetTeamPlacement:
    meet_name: str
    meet_date: Optional[str]
    season: int
    gender: str
    team: str
    team_place: Optional[int]
    team_points: Optional[int]
    meet_kind: str = "invitational"    # invitational|conference|regional|national


@dataclasses.dataclass
class HSMark:
    """Best-effort high-school PR linked to a college athlete."""
    athlete_name: str
    college_team: str
    gender: str
    event: str                         # e.g. "5000m" / "3200m" / "1600m"
    mark_seconds: Optional[float]
    hs_grad_year: Optional[int]
    source: str                        # "athletic.net" | "manual" | ...
    match_confidence: float = 0.0      # 0..1 fuzzy-link confidence
