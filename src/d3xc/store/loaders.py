"""Loaders: move config + scraped records into the normalized DB."""
from __future__ import annotations

import csv
import logging
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from d3xc import config
from d3xc.scrape.records import HSMark, MeetTeamPlacement, RaceResult, RosterEntry
from d3xc.store.db import (
    Athlete,
    CoachTenure,
    HSMarkRow,
    Result,
    Team,
    TeamPlacement,
)

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# config -> db
# --------------------------------------------------------------------------
def upsert_teams(session: Session) -> dict[str, Team]:
    """Ensure every team in teams.yaml exists (tracked=True); return name->Team."""
    existing = {t.name: t for t in session.scalars(select(Team)).all()}
    for t in config.load_teams():
        if t.name not in existing:
            row = Team(name=t.name, conference=t.conference, tracked=True)
            session.add(row)
            existing[t.name] = row
        else:
            existing[t.name].conference = t.conference
            existing[t.name].tracked = True
    session.flush()
    return existing


def get_or_create_team(session: Session, name: str, conference: str = "(national)",
                       tracked: bool = False) -> Team:
    """Fetch a team by name or create it (used for national-context teams)."""
    t = session.scalar(select(Team).where(Team.name == name))
    if t is None:
        t = Team(name=name, conference=conference, tracked=tracked)
        session.add(t)
        session.flush()
    return t


def load_coaches_csv(session: Session, path=None) -> int:
    """Load curated coaching tenures. Rows referencing unknown teams are skipped.

    This is a full reload of curated data, so existing tenures are cleared first
    (idempotent across repeated scrape runs)."""
    path = path or config.COACHES_CSV
    session.query(CoachTenure).delete()
    session.flush()
    teams = {t.name: t for t in session.scalars(select(Team)).all()}
    added = 0
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(row for row in fh if not row.lstrip().startswith("#"))
        for r in reader:
            team = teams.get(r["team"].strip())
            if not team:
                log.warning("coaches.csv: unknown team %r, skipping", r["team"])
                continue
            session.add(
                CoachTenure(
                    team_id=team.id,
                    gender=(r.get("gender") or "both").strip() or "both",
                    coach_name=r["coach_name"].strip(),
                    start_year=int(r["start_year"]),
                    end_year=int(r["end_year"]) if r.get("end_year", "").strip() else None,
                    source=(r.get("source") or "").strip() or None,
                )
            )
            added += 1
    session.flush()
    return added


# --------------------------------------------------------------------------
# scraped records -> db
# --------------------------------------------------------------------------
def _team_by_name(session: Session, name: str) -> Optional[Team]:
    return session.scalar(select(Team).where(Team.name == name))


def get_or_create_athlete(
    session: Session,
    *,
    name: str,
    gender: str,
    team: Team,
    tfrrs_athlete_id: Optional[str] = None,
) -> Athlete:
    # Case-insensitive match: athlete pages render names in ALL-CAPS while meet
    # pages use Title Case; treat them as the same athlete.
    stmt = select(Athlete).where(
        func.lower(Athlete.name) == name.lower(),
        Athlete.team_id == team.id,
        Athlete.gender == gender,
    )
    a = session.scalar(stmt)
    if a is None:
        a = Athlete(
            name=_prettify_name(name), gender=gender, team_id=team.id,
            tfrrs_athlete_id=tfrrs_athlete_id,
        )
        session.add(a)
        session.flush()
    else:
        if tfrrs_athlete_id and not a.tfrrs_athlete_id:
            a.tfrrs_athlete_id = tfrrs_athlete_id
        # prefer a Title-Case display name over an ALL-CAPS one
        if a.name.isupper() and not name.isupper():
            a.name = _prettify_name(name)
    return a


def _prettify_name(name: str) -> str:
    """Normalize an ALL-CAPS name to Title Case, preserving apostrophes/hyphens."""
    if not name.isupper():
        return name
    import re as _re
    return _re.sub(r"[A-Za-z]+('[A-Za-z]+)?", lambda m: m.group(0).capitalize(), name.title())


def load_roster(session: Session, entries: Iterable[RosterEntry]) -> int:
    n = 0
    for e in entries:
        team = _team_by_name(session, e.team)
        if not team:
            continue
        get_or_create_athlete(
            session,
            name=e.athlete_name,
            gender=e.gender,
            team=team,
            tfrrs_athlete_id=e.tfrrs_athlete_id,
        )
        n += 1
    session.flush()
    return n


def load_results(session: Session, results: Iterable[RaceResult],
                 dedup: bool = False) -> int:
    """Insert race results. With dedup=True, skip rows that already exist
    (same athlete/season/meet/time) so athlete-page and meet-page scrapes can
    be combined without double-counting."""
    n = 0
    for r in results:
        team = _team_by_name(session, r.team)
        if not team:
            continue
        athlete = get_or_create_athlete(
            session,
            name=r.athlete_name,
            gender=r.gender,
            team=team,
            tfrrs_athlete_id=r.tfrrs_athlete_id,
        )
        if dedup:
            exists = session.scalar(
                select(Result.id).where(
                    Result.athlete_id == athlete.id,
                    Result.season == r.season,
                    Result.meet_name == r.meet_name,
                    Result.mark_seconds == r.mark_seconds,
                )
            )
            if exists:
                continue
        session.add(
            Result(
                athlete_id=athlete.id,
                team_id=team.id,
                gender=r.gender,
                season=r.season,
                meet_name=r.meet_name,
                meet_date=r.meet_date,
                distance_m=r.distance_m,
                mark_seconds=r.mark_seconds,
                place_overall=r.place_overall,
            )
        )
        n += 1
    session.flush()
    return n


def load_team_placements(session: Session, placements: Iterable[MeetTeamPlacement],
                         dedup: bool = False) -> int:
    n = 0
    for p in placements:
        team = _team_by_name(session, p.team)
        if not team:
            continue
        if dedup:
            exists = session.scalar(
                select(TeamPlacement.id).where(
                    TeamPlacement.team_id == team.id,
                    TeamPlacement.gender == p.gender,
                    TeamPlacement.season == p.season,
                    TeamPlacement.meet_name == p.meet_name,
                )
            )
            if exists:
                continue
        session.add(
            TeamPlacement(
                team_id=team.id,
                gender=p.gender,
                season=p.season,
                meet_name=p.meet_name,
                meet_kind=p.meet_kind,
                team_place=p.team_place,
                team_points=p.team_points,
            )
        )
        n += 1
    session.flush()
    return n


def load_hs_marks(session: Session, marks: Iterable[HSMark]) -> int:
    n = 0
    for m in marks:
        team = _team_by_name(session, m.college_team)
        if not team:
            continue
        athlete = session.scalar(
            select(Athlete).where(
                Athlete.name == m.athlete_name,
                Athlete.team_id == team.id,
                Athlete.gender == m.gender,
            )
        )
        session.add(
            HSMarkRow(
                athlete_id=athlete.id if athlete else None,
                athlete_name=m.athlete_name,
                college_team_id=team.id,
                gender=m.gender,
                event=m.event,
                mark_seconds=m.mark_seconds,
                hs_grad_year=m.hs_grad_year,
                source=m.source,
                match_confidence=m.match_confidence,
            )
        )
        n += 1
    session.flush()
    return n


def load_hs_marks_csv(session: Session, path=None) -> int:
    """Load curated HS marks from config/hs_marks.csv and link to college
    athletes by exact name+team+gender (curated => confidence 1.0). Rows for
    unknown athlete/team combinations are skipped."""
    from d3xc.scrape.timeutil import time_to_seconds
    path = path or config.HS_MARKS_CSV
    if not path.exists():
        return 0
    marks = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(row for row in fh if not row.lstrip().startswith("#"))
        for r in reader:
            secs = time_to_seconds(r["mark"]) if r.get("mark") else None
            if secs is None:
                continue
            gy = r.get("hs_grad_year", "").strip()
            marks.append(HSMark(
                athlete_name=r["athlete_name"].strip(),
                college_team=r["college_team"].strip(),
                gender=r["gender"].strip(),
                event=r["event"].strip(),
                mark_seconds=secs,
                hs_grad_year=int(gy) if gy else None,
                source=(r.get("source") or "curated").strip(),
                match_confidence=1.0,
            ))
    return load_hs_marks(session, marks)


def update_athlete_origins(session: Session, team_name: str, gender: str,
                           records) -> int:
    """Update hometown/high_school/home_state for athletes on a team, matching
    roster entries by case-insensitive name. Returns number updated."""
    team = _team_by_name(session, team_name)
    if not team:
        return 0
    n = 0
    for r in records:
        a = session.scalar(select(Athlete).where(
            func.lower(Athlete.name) == r["name"].lower(),
            Athlete.team_id == team.id, Athlete.gender == gender))
        if not a:
            continue
        if r.get("hometown"):
            a.hometown = r["hometown"]
        if r.get("high_school"):
            a.high_school = r["high_school"]
        if r.get("home_state"):
            a.home_state = r["home_state"]
        n += 1
    session.flush()
    return n


def load_meet_all_teams(session: Session, parsed: dict, dedup: bool = True):
    """Load a full meet field (all teams), creating national-context teams
    (tracked=False) for any not already present. Ohio teams keep tracked=True."""
    names = ({p.team for p in parsed["team_placements"]}
             | {r.team for r in parsed["individual_results"]})
    for name in names:
        get_or_create_team(session, name)          # tracked=False for new teams
    session.flush()
    p = load_team_placements(session, [x for x in parsed["team_placements"] if x.gender], dedup=dedup)
    i = load_results(session, [x for x in parsed["individual_results"] if x.gender], dedup=dedup)
    return p, i
