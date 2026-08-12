"""Scrape NCAA DIII Cross Country National Championship results (full field).

Bounded national expansion: instead of every D3 team, we ingest only the ~32
qualifying teams at each year's national meet. National teams are stored with
tracked=False so they provide *context* (where Ohio programs rank, All-Americans)
without entering the Ohio ratings/development/coaching analyses.

Meet IDs were harvested from the crawl cache (2020 cancelled — COVID).

    python scripts/scrape_nationals.py
"""
from __future__ import annotations

import logging

import _bootstrap  # noqa: F401

from d3xc.scrape import tfrrs
from d3xc.scrape.http import PoliteSession
from d3xc.store import loaders
from d3xc.store.db import get_sessionmaker, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("nationals")

# NCAA DIII XC National Championship TFRRS meet ids by season
NATIONAL_MEETS = {
    2016: 11260, 2017: 13424, 2018: 15028, 2019: 16726,
    2021: 19297, 2022: 21228, 2023: 23317, 2024: 25327, 2025: 27292,
}
SLUG = "NCAA_Division_III_Cross_Country_Championships"


def main():
    engine = init_db()
    Session = get_sessionmaker(engine)
    http = PoliteSession(delay=0.5)
    with Session() as session:
        loaders.upsert_teams(session)
        session.commit()
        tot_p = tot_i = tot_teams = 0
        for season, mid in NATIONAL_MEETS.items():
            url = tfrrs.meet_result_url(mid, SLUG)
            try:
                parsed = tfrrs.parse_meet(http.get(url))     # full field, no filter
            except Exception as exc:  # noqa: BLE001
                log.warning("nationals %s failed: %s", season, exc)
                continue
            if parsed["meet_kind"] != "national" or parsed["season"] != season:
                log.warning("nationals %s: parsed season=%s kind=%s (skipping)",
                            season, parsed["season"], parsed["meet_kind"])
                continue
            n_teams = len({p.team for p in parsed["team_placements"] if p.gender})
            p, i = loaders.load_meet_all_teams(session, parsed, dedup=True)
            session.commit()
            tot_p += p
            tot_i += i
            tot_teams = max(tot_teams, n_teams)
            log.info("%s nationals: %d teams, +%d placements, +%d individuals",
                     season, n_teams, p, i)
        log.info("Done. placements=%d individuals=%d", tot_p, tot_i)


if __name__ == "__main__":
    main()
