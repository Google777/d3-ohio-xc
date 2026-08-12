"""Scrape athlete origin (hometown / home state / high school) from college
roster pages and attach it to athletes in the DB.

Sources roster pages from config/athletics_sites.yaml (Sidearm layout). Scrapes
the current roster plus historical seasons so graduated athletes are covered,
matching by name+team+gender. Polite + cached.

    python scripts/scrape_origins.py --delay 0.5
    python scripts/scrape_origins.py --years 2019,2022,2025   # limit seasons
"""
from __future__ import annotations

import argparse
import logging

import yaml

import _bootstrap  # noqa: F401

from d3xc import config
from d3xc.scrape import rosters
from d3xc.scrape.http import PoliteSession
from d3xc.store import loaders
from d3xc.store.db import get_sessionmaker, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("origins")

SPORT = {"men": ["mens-cross-country", "cross-country"],
         "women": ["womens-cross-country", "cross-country"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--years", default=None, help="comma list; default current+2016..2025")
    args = ap.parse_args()

    with open(config.CONFIG_DIR / "athletics_sites.yaml", encoding="utf-8") as fh:
        sites = yaml.safe_load(fh)["sites"]
    years = ([None] + [int(y) for y in args.years.split(",")]) if args.years \
        else [None] + list(config.SEASONS)

    engine = init_db()
    Session = get_sessionmaker(engine)
    http = PoliteSession(delay=args.delay)
    total = 0
    with Session() as session:
        for team, base in sites.items():
            team_total = 0
            for gender, paths in SPORT.items():
                for sport in paths:
                    for year in years:
                        url = rosters.roster_url(base, sport, year)
                        try:
                            recs = rosters.parse_roster(http.get(url))
                        except Exception:  # noqa: BLE001
                            continue
                        if recs:
                            team_total += loaders.update_athlete_origins(session, team, gender, recs)
                    session.commit()
            total += team_total
            log.info("%s: +%d origin updates", team, team_total)
    log.info("Done. total origin updates=%d", total)


if __name__ == "__main__":
    main()
