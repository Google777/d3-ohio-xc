"""Orchestrate a live TFRRS scrape into the DB.

This is the real-data path (the seed script is the synthetic path). It is polite
by construction: a shared throttled+cached session, and it stops early with
--limit for smoke tests.

    python scripts/run_scrape.py --limit 2          # try 2 teams
    python scripts/run_scrape.py                     # all teams (slow!)

NOTE: team slugs in config/teams.yaml are unverified best-effort guesses. Run
`python scripts/resolve_slugs.py` first (or fix them by hand) for a full scrape.
Unresolved/blocked pages are logged and skipped rather than crashing the run.
"""
from __future__ import annotations

import argparse
import logging

import _bootstrap  # noqa: F401

from d3xc import config
from d3xc.scrape import tfrrs
from d3xc.scrape.http import PoliteSession
from d3xc.store import loaders
from d3xc.store.db import get_sessionmaker, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("run_scrape")


def scrape_team(session_http, team, gender: str, max_athletes=None):
    """Fetch a team page, then each athlete's results. Returns (roster, results)."""
    url = tfrrs.team_url(team.tfrrs_slug, gender)
    try:
        html = session_http.get(url)
    except Exception as exc:  # network/HTTP/parse issues shouldn't kill the run
        log.warning("team fetch failed %s (%s): %s", team.name, gender, exc)
        return [], []

    roster = tfrrs.parse_team_roster(html, team.name, gender, config.LAST_SEASON)
    results = []
    links = tfrrs.discover_athlete_links(html)
    if max_athletes:
        links = links[:max_athletes]
    for aid, _name in links:
        try:
            ahtml = session_http.get(tfrrs.athlete_url(aid))
            results.extend(
                tfrrs.parse_athlete_xc(
                    ahtml, team.name, gender, only_seasons=config.SEASONS
                )
            )
        except Exception as exc:
            log.warning("athlete fetch failed %s: %s", aid, exc)
    return roster, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="max teams to scrape")
    ap.add_argument("--fresh", action="store_true", help="drop & recreate DB first")
    ap.add_argument("--delay", type=float, default=config.REQUEST_DELAY_SECONDS,
                    help="seconds between live requests")
    ap.add_argument("--genders", default="men,women",
                    help="comma list: men,women")
    ap.add_argument("--max-athletes", type=int, default=None,
                    help="cap athlete pages per team")
    ap.add_argument("--teams", default=None,
                    help="comma list of team names to include (default: all)")
    args = ap.parse_args()

    engine = init_db(drop=args.fresh)
    Session = get_sessionmaker(engine)
    http = PoliteSession(delay=args.delay)

    genders = [g.strip() for g in args.genders.split(",") if g.strip()]
    teams = config.load_teams()
    if args.teams:
        wanted = {t.strip() for t in args.teams.split(",")}
        teams = [t for t in teams if t.name in wanted]
    if args.limit:
        teams = teams[: args.limit]

    with Session() as session:
        loaders.upsert_teams(session)
        loaders.load_coaches_csv(session)
        session.commit()

        total_r = total_a = 0
        for team in teams:
            for gender in genders:
                roster, results = scrape_team(http, team, gender, args.max_athletes)
                total_a += loaders.load_roster(session, roster)
                total_r += loaders.load_results(session, results)
                session.commit()
                log.info("%s %s: +%d roster, +%d results",
                         team.name, gender, len(roster), len(results))
        log.info("Done. roster entries=%d, results=%d", total_a, total_r)


if __name__ == "__main__":
    main()
