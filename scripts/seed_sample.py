"""Seed the DB with realistic *synthetic* data for all Ohio D3 teams.

This lets the store -> analyze -> dashboard stages run end-to-end WITHOUT live
scraping (useful for demos, CI, and development). Data is plausible but invented:
  * per team/gender, a roster that turns over each season (FR->SR progression),
  * individual season-best times that improve with class year + a team trend,
  * multiple meets per season at 5k/8k/6k distances,
  * conference/regional/national placements with per-team multi-year arcs,
  * a handful of HS marks linked to college athletes with confidence scores.

Deterministic via a fixed RNG seed so tests are stable.
"""
from __future__ import annotations

import random

import _bootstrap  # noqa: F401  (adds src to path)

from d3xc import config
from d3xc.scrape.records import HSMark, MeetTeamPlacement, RaceResult
from d3xc.store import loaders
from d3xc.store.db import get_sessionmaker, init_db

RNG = random.Random(20260807)

# gender -> (baseline std-distance seconds for a solid D3 #1, spread to #7)
BASELINE = {
    "men": 1500.0,    # ~25:00 for 8k
    "women": 1380.0,  # ~23:00 for 6k
}
CLASS_PROGRESSION = {"FR": 0.0, "SO": -18.0, "JR": -30.0, "SR": -40.0}
CLASS_ORDER = ["FR", "SO", "JR", "SR"]
CLASS_SIZE = 6   # freshmen recruited per team/gender/season

FIRST_NAMES = ["Alex", "Jordan", "Sam", "Casey", "Riley", "Drew", "Taylor",
               "Morgan", "Jamie", "Quinn", "Avery", "Cameron", "Reese", "Blake",
               "Hayden", "Emerson", "Parker", "Rowan", "Sawyer", "Finley"]
LAST_NAMES = ["Miller", "Davis", "Wilson", "Fischer", "Kowalski", "Nguyen",
              "Bauer", "Reyes", "OBrien", "Schmidt", "Patel", "Novak",
              "Carter", "Hughes", "Bennett", "Sullivan", "Meyer", "Foster",
              "Grant", "Klein", "Marsh", "Underwood", "Vance", "Whitaker"]

MEETS = [
    ("Early Season Open", 5000, "invitational"),
    ("All-Ohio Championships", 8000, "invitational"),
    ("Inter-Regional Rumble", 8000, "invitational"),
    ("Conference Championships", 8000, "conference"),
    ("NCAA Great Lakes Regional", 8000, "regional"),
    ("NCAA Division III Championships", 8000, "national"),
]


def _dist_for(gender: str, nominal: int) -> int:
    if nominal == 8000 and gender == "women":
        return 6000
    return nominal


def _make_name(used: set) -> str:
    for _ in range(200):
        n = f"{RNG.choice(FIRST_NAMES)} {RNG.choice(LAST_NAMES)}"
        if n not in used:
            used.add(n)
            return n
    n = f"{RNG.choice(FIRST_NAMES)} {RNG.choice(LAST_NAMES)}{RNG.randint(1, 999)}"
    used.add(n)
    return n


def seed() -> dict:
    engine = init_db(drop=True)
    Session = get_sessionmaker(engine)
    stats = {"athletes": 0, "results": 0, "placements": 0, "hs": 0, "coaches": 0}

    with Session() as session:
        teams = loaders.upsert_teams(session)
        session.commit()
        stats["coaches"] = loaders.load_coaches_csv(session)
        session.commit()

        team_list = list(teams.values())
        # each team gets a "trajectory": improving, declining, or steady
        trajectory = {t.name: RNG.choice([-1, 0, 1]) for t in team_list}
        # strength percentile: better teams place higher at regionals/nationals
        strength = {t.name: RNG.uniform(0, 1) for t in team_list}

        results: list[RaceResult] = []
        placements: list[MeetTeamPlacement] = []
        hs_marks: list[HSMark] = []

        for t in team_list:
            for gender in ("men", "women"):
                base = BASELINE[gender]
                used_names = set()
                # recruiting-class model: each season brings CLASS_SIZE freshmen
                # who run a 4-year arc -> full scoring squads every season.
                roster = []
                for debut in config.SEASONS:
                    for _ in range(CLASS_SIZE):
                        talent = RNG.gauss(0, 22)  # negative = faster
                        roster.append({
                            "name": _make_name(used_names),
                            "debut": debut,
                            "talent": talent,
                    })

                for si, season in enumerate(config.SEASONS):
                    team_trend = trajectory[t.name] * si * 3.0  # sec/yr drift
                    season_athletes = []
                    for r in roster:
                        age = season - r["debut"]
                        if age < 0 or age > 3:
                            continue
                        cls = CLASS_ORDER[age]
                        prog = CLASS_PROGRESSION[cls]
                        season_best = (
                            base + r["talent"] + prog - team_trend
                            + RNG.gauss(0, 6)
                        )
                        season_athletes.append((r["name"], cls, season_best))
                        # emit 3-5 races at varying distances around season_best
                        for meet_name, nominal, kind in RNG.sample(MEETS, k=RNG.randint(3, len(MEETS))):
                            dist = _dist_for(gender, nominal)
                            std_km = 8.0 if gender == "men" else 6.0
                            pace = season_best / std_km
                            noise = RNG.gauss(0, 4)
                            mark = pace * (dist / 1000.0) + noise
                            results.append(RaceResult(
                                team=t.name, gender=gender, season=season,
                                athlete_name=r["name"], tfrrs_athlete_id=None,
                                meet_name=f"{season} {meet_name}",
                                meet_date=f"{season}-10-15",
                                distance_m=dist, mark_seconds=round(mark, 1),
                            ))
                    stats["athletes"] += 0  # counted at load

                    # team placements: derive a score rank from top-5 season bests
                    top5 = sorted(a[2] for a in season_athletes)[:5]
                    if len(top5) == 5:
                        team_quality = sum(top5) / 5 - strength[t.name] * 20
                        # map quality to placements (lower time -> better place)
                        conf_place = _rank_bucket(team_quality, base, spread=8)
                        reg_place = _rank_bucket(team_quality, base, spread=35)
                        placements.append(MeetTeamPlacement(
                            meet_name=f"{season} Conference Championships",
                            meet_date=f"{season}-11-01", season=season,
                            gender=gender, team=t.name, team_place=conf_place,
                            team_points=conf_place * 25 + RNG.randint(0, 20),
                            meet_kind="conference",
                        ))
                        placements.append(MeetTeamPlacement(
                            meet_name=f"{season} NCAA Great Lakes Regional",
                            meet_date=f"{season}-11-14", season=season,
                            gender=gender, team=t.name, team_place=reg_place,
                            team_points=reg_place * 12 + RNG.randint(0, 30),
                            meet_kind="regional",
                        ))
                        # only strong teams qualify for nationals
                        if reg_place <= 3 and strength[t.name] > 0.7:
                            placements.append(MeetTeamPlacement(
                                meet_name=f"{season} NCAA DIII Championships",
                                meet_date=f"{season}-11-22", season=season,
                                gender=gender, team=t.name,
                                team_place=RNG.randint(1, 32),
                                team_points=RNG.randint(50, 600),
                                meet_kind="national",
                            ))

                # HS marks for the 3 fastest athletes on this squad
                fastest = sorted(roster, key=lambda r: r["talent"])[:3]
                for r in fastest:
                    if gender == "men":
                        event, hs_secs = "3200m", RNG.uniform(560, 640)  # ~9:20-10:40
                    else:
                        event, hs_secs = "3200m", RNG.uniform(640, 720)
                    hs_marks.append(HSMark(
                        athlete_name=r["name"], college_team=t.name, gender=gender,
                        event=event, mark_seconds=round(hs_secs, 1),
                        hs_grad_year=r["debut"], source="synthetic",
                        match_confidence=round(RNG.uniform(0.7, 0.99), 3),
                    ))

        stats["results"] = loaders.load_results(session, results)
        stats["placements"] = loaders.load_team_placements(session, placements)
        stats["hs"] = loaders.load_hs_marks(session, hs_marks)
        session.commit()

        from sqlalchemy import func, select
        from d3xc.store.db import Athlete
        stats["athletes"] = session.scalar(select(func.count(Athlete.id)))

    return stats


def _rank_bucket(team_quality: float, base: float, spread: float) -> int:
    """Map a team-quality time to a placement (1 = best). Deterministic-ish."""
    # faster-than-base -> better place; scale by spread
    delta = team_quality - base
    place = int(round(spread / 2 + delta / 4))
    return max(1, min(spread, place))


if __name__ == "__main__":
    s = seed()
    print("Seed complete:", s)
