"""Rebuild the DB by parsing EVERY cached HTML file as a potential meet page.

Link-based discovery misses meets that are cached but not linked by any other
cached page (e.g. the 2017 national championship). Iterating the cache files
directly captures every meet we ever fetched. Non-meet pages (athlete/team
pages) yield no team-results headings and are skipped.
"""
from __future__ import annotations

import logging

import _bootstrap  # noqa: F401

from d3xc import config
from d3xc.scrape import tfrrs
from d3xc.store import loaders
from d3xc.store.db import get_sessionmaker, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("rebuild")


def main():
    engine = init_db(drop=True)          # fresh
    Session = get_sessionmaker(engine)
    known = {t.name for t in config.load_teams()}
    seasons = set(config.SEASONS)

    files = sorted(config.CACHE_DIR.glob("*.html"))
    log.info("scanning %d cached files", len(files))
    with Session() as session:
        loaders.upsert_teams(session)
        loaders.load_coaches_csv(session)
        loaders.load_hs_marks_csv(session)
        session.commit()

        meets = tot_p = tot_i = 0
        by_kind_season: dict = {}
        for fp in files:
            html = fp.read_text(errors="replace")
            if "Team Results" not in html and "Individual Results" not in html:
                continue
            try:
                m = tfrrs.parse_meet(html, known_teams=known)
            except Exception:  # noqa: BLE001
                continue
            if not m["team_placements"] and not m["individual_results"]:
                continue
            if m["season"] not in seasons:
                continue
            p = loaders.load_team_placements(
                session, [x for x in m["team_placements"] if x.gender], dedup=True)
            i = loaders.load_results(
                session, [x for x in m["individual_results"] if x.gender], dedup=True)
            if p or i:
                meets += 1
                tot_p += p
                tot_i += i
                key = (m["meet_kind"], m["season"])
                by_kind_season[key] = by_kind_season.get(key, 0) + p
            session.commit()

        log.info("Done. meets=%d placements=%d individuals=%d", meets, tot_p, tot_i)
        nat = {s: n for (k, s), n in sorted(by_kind_season.items()) if k == "national"}
        log.info("national placements by season: %s", nat)


if __name__ == "__main__":
    main()
