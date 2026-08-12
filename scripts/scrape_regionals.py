"""Load NCAA Great Lakes Regional full fields (all teams) from the HTTP cache.

Like scrape_nationals, but for the regional meet. Non-tracked regional teams
(Calvin, Hope, Trine, ...) are stored tracked=False as context, enabling an
ACTUAL regional qualifying bar. Parses every cached meet file, keeping the ones
classified 'regional' in the analysis window.

    python scripts/scrape_regionals.py
"""
from __future__ import annotations

import logging

import _bootstrap  # noqa: F401

from d3xc import config
from d3xc.scrape import tfrrs
from d3xc.store import loaders
from d3xc.store.db import get_sessionmaker, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("regionals")


def main():
    engine = init_db()
    Session = get_sessionmaker(engine)
    seasons = set(config.SEASONS)
    files = sorted(config.CACHE_DIR.glob("*.html"))
    with Session() as session:
        loaders.upsert_teams(session)
        session.commit()
        seen, meets, tot_p, tot_i = set(), 0, 0, 0
        for fp in files:
            html = fp.read_text(errors="replace")
            if "Team Results" not in html or "Region" not in html:
                continue
            try:
                m = tfrrs.parse_meet(html)          # full field, no filter
            except Exception:  # noqa: BLE001
                continue
            if m["meet_kind"] != "regional" or m["season"] not in seasons:
                continue
            nm = m["meet_name"].lower()
            if not ("division iii" in nm or "diii" in nm or "d3" in nm):
                continue                        # exclude D1/D2 regionals
            key = (m["season"], m["meet_name"])
            if key in seen:
                continue
            seen.add(key)
            p, i = loaders.load_meet_all_teams(session, m, dedup=True)
            session.commit()
            meets += 1
            tot_p += p
            tot_i += i
            log.info("%s %s: +%d placements, +%d individuals",
                     m["season"], m["meet_name"][:45], p, i)
        log.info("Done. regional meets=%d placements=%d individuals=%d",
                 meets, tot_p, tot_i)


if __name__ == "__main__":
    main()
