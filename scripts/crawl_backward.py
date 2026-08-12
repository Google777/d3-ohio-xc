"""Backward crawl: extend meet coverage back in time along Ohio D3 lineages.

Athlete pages only reach as far back as *current* rosters. But a 2022 senior's
page links to the 2019-2021 meets they ran; those meets contain older Ohio D3
athletes whose pages link to still-earlier meets. Walking this graph -- but only
following athletes on our 21 tracked teams -- extends coverage backward toward
FIRST_SEASON without drifting into all of national D3.

BFS over two frontiers (meets, athletes), bounded by fetch budgets:

    python scripts/crawl_backward.py --max-athletes 500 --max-meets 400 --delay 0.5

Loads team placements + individual results (de-duplicated) as it goes and commits
per meet, so partial progress persists. Re-running resumes from the warm cache.
"""
from __future__ import annotations

import argparse
import heapq
import itertools
import logging
from collections import deque

import _bootstrap  # noqa: F401

from d3xc import config
from d3xc.scrape import tfrrs
from d3xc.scrape.http import PoliteSession
from d3xc.store import loaders
from d3xc.store.db import get_sessionmaker, init_db
from scrape_meets import discover_from_cache

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("crawl_backward")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-athletes", type=int, default=500)
    ap.add_argument("--max-meets", type=int, default=400)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--no-individuals", action="store_true")
    args = ap.parse_args()

    engine = init_db()
    Session = get_sessionmaker(engine)
    http = PoliteSession(delay=args.delay)
    known = {t.name for t in config.load_teams()}
    seasons = set(config.SEASONS)

    meet_q = deque(discover_from_cache())
    # athlete frontier is a min-heap keyed by (surfacing meet season) so we
    # expand the OLDEST lineages first, directing the budget back in time.
    athlete_heap: list[tuple[int, int, str]] = []
    counter = itertools.count()

    def push_athlete(aid: str, season: int | None):
        heapq.heappush(athlete_heap, (season or 9999, next(counter), aid))

    seen_meets: set[str] = set()
    seen_athletes: set[str] = set()
    n_meet_fetch = n_ath_fetch = tot_p = tot_i = 0
    season_hits: dict[int, int] = {}

    with Session() as session:
        loaders.upsert_teams(session)
        session.commit()

        while meet_q or athlete_heap:
            # 1) drain meets first: load data + seed athlete frontier
            if meet_q and n_meet_fetch < args.max_meets:
                url = meet_q.popleft()
                if url in seen_meets:
                    continue
                seen_meets.add(url)
                try:
                    html = http.get(url)
                    n_meet_fetch += 1
                    parsed = tfrrs.parse_meet(html, known_teams=known)
                except Exception as exc:  # noqa: BLE001
                    log.warning("meet failed %s: %s", url, exc)
                    continue
                season = parsed["season"]
                if season in seasons:
                    placements = [p for p in parsed["team_placements"] if p.gender]
                    tot_p += loaders.load_team_placements(session, placements, dedup=True)
                    if not args.no_individuals:
                        inds = [r for r in parsed["individual_results"] if r.gender]
                        tot_i += loaders.load_results(session, inds, dedup=True)
                    session.commit()
                    season_hits[season] = season_hits.get(season, 0) + 1
                # follow our-team athletes from this meet (oldest expanded first)
                for aid in tfrrs.discover_team_athletes(html, known):
                    if aid not in seen_athletes:
                        push_athlete(aid, season)
                continue

            # 2) expand the oldest-lineage athlete: discover their earlier meets
            if athlete_heap and n_ath_fetch < args.max_athletes:
                _, _, aid = heapq.heappop(athlete_heap)
                if aid in seen_athletes:
                    continue
                seen_athletes.add(aid)
                try:
                    html = http.get(tfrrs.athlete_url(aid))
                    n_ath_fetch += 1
                except Exception as exc:  # noqa: BLE001
                    log.warning("athlete failed %s: %s", aid, exc)
                    continue
                for murl in tfrrs.discover_meet_links(html):
                    if murl not in seen_meets:
                        meet_q.append(murl)
                if n_ath_fetch % 25 == 0:
                    log.info("progress: %d athletes, %d meets, seasons=%s",
                             n_ath_fetch, n_meet_fetch, dict(sorted(season_hits.items())))
                continue

            break  # budgets exhausted

        log.info("Done. meets=%d athletes=%d placements=%d individuals=%d",
                 n_meet_fetch, n_ath_fetch, tot_p, tot_i)
        log.info("season coverage (meets loaded per season): %s",
                 dict(sorted(season_hits.items())))


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
