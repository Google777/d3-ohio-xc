"""Targeted backfill for specific missing championship meets (e.g. 2019 OAC,
2016/2017 NCAC). Seeds from already-cached 2016-2019 championship meets, follows
our-team athletes who ran them, and loads any in-window conference/regional/
national meets those athletes link that aren't in the DB yet.
"""
from __future__ import annotations

import logging

import _bootstrap  # noqa: F401

from d3xc import config
from d3xc.scrape import tfrrs
from d3xc.scrape.http import PoliteSession
from d3xc.store import loaders
from d3xc.store.db import get_sessionmaker, init_db
from scrape_meets import discover_from_cache

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("backfill")

TARGET = {2016, 2017, 2018, 2019}
ATHLETE_BUDGET = 120


def main():
    engine = init_db()
    Session = get_sessionmaker(engine)
    http = PoliteSession(delay=0.4)
    known = {t.name for t in config.load_teams()}

    seen_meets = set(discover_from_cache())
    seed_athletes: list[str] = []
    seed_seen = set()

    # 1) seed from cached championship meets in the target years
    for url in list(seen_meets):
        try:
            html = http.get(url)
            m = tfrrs.parse_meet(html, known_teams=known)
        except Exception:  # noqa: BLE001
            continue
        if m["season"] in TARGET and m["meet_kind"] in ("regional", "conference", "national"):
            for aid in tfrrs.discover_team_athletes(html, known):
                if aid not in seed_seen:
                    seed_seen.add(aid)
                    seed_athletes.append(aid)
    log.info("seeded %d athletes from cached %s championship meets", len(seed_athletes), sorted(TARGET))

    # 2) expand athletes -> discover + load missing in-window meets
    with Session() as session:
        loaders.upsert_teams(session)
        session.commit()
        tot_p = tot_i = new_meets = 0
        for i, aid in enumerate(seed_athletes[:ATHLETE_BUDGET]):
            try:
                ah = http.get(tfrrs.athlete_url(aid))
            except Exception:  # noqa: BLE001
                continue
            for murl in tfrrs.discover_meet_links(ah):
                if murl in seen_meets:
                    continue
                seen_meets.add(murl)
                try:
                    mm = tfrrs.parse_meet(http.get(murl), known_teams=known)
                except Exception:  # noqa: BLE001
                    continue
                if mm["season"] in TARGET and mm["meet_kind"] in ("conference", "regional", "national"):
                    p = loaders.load_team_placements(
                        session, [x for x in mm["team_placements"] if x.gender], dedup=True)
                    ii = loaders.load_results(
                        session, [x for x in mm["individual_results"] if x.gender], dedup=True)
                    session.commit()
                    if p or ii:
                        new_meets += 1
                        log.info("+ %s %s: %s (+%d pl, +%d ind)",
                                 mm["season"], mm["meet_kind"], mm["meet_name"][:45], p, ii)
        log.info("Done. new meets loaded=%d placements=%d individuals=%d",
                 new_meets, tot_p, tot_i)


if __name__ == "__main__":
    main()
