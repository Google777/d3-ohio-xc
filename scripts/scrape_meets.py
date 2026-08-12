"""Scrape TFRRS XC meet-results pages -> team placements + individual results.

Discovery: meet links are harvested from already-cached athlete/team pages
(``data/raw/http_cache``), so no extra network is needed to find meets. You can
also pass explicit meet URLs with --meets.

    python scripts/scrape_meets.py                     # discover from cache, scrape all
    python scripts/scrape_meets.py --kinds conference,regional,national
    python scripts/scrape_meets.py --limit 5 --no-individuals

This ADDS to the existing DB (run run_scrape.py first for roster/athlete data).
Team placements are captured for ALL tracked teams present in each meet, even
teams whose rosters were not scraped. Individual results are de-duplicated
against athlete-page results.
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
log = logging.getLogger("scrape_meets")


def discover_from_cache() -> list[str]:
    """Harvest unique XC meet URLs from every cached HTML page."""
    urls: dict[str, None] = {}
    if not config.CACHE_DIR.exists():
        return []
    for f in config.CACHE_DIR.glob("*.html"):
        try:
            html = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for u in tfrrs.discover_meet_links(html):
            urls.setdefault(u, None)
    return list(urls)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.7)
    ap.add_argument("--limit", type=int, default=None, help="max meets to scrape")
    ap.add_argument("--meets", default=None, help="comma list of explicit meet URLs")
    ap.add_argument("--kinds", default=None,
                    help="filter to meet kinds, e.g. conference,regional,national")
    ap.add_argument("--no-individuals", action="store_true",
                    help="load team placements only")
    args = ap.parse_args()

    engine = init_db()          # add to existing DB
    Session = get_sessionmaker(engine)
    http = PoliteSession(delay=args.delay)

    meet_urls = discover_from_cache()
    if args.meets:
        meet_urls += [u.strip() for u in args.meets.split(",") if u.strip()]
    # dedupe preserving order
    meet_urls = list(dict.fromkeys(meet_urls))
    if args.limit:
        meet_urls = meet_urls[: args.limit]
    kinds = set(args.kinds.split(",")) if args.kinds else None
    log.info("discovered %d candidate meet URLs", len(meet_urls))

    known = {t.name for t in config.load_teams()}
    seasons = set(config.SEASONS)

    with Session() as session:
        loaders.upsert_teams(session)
        loaders.load_coaches_csv(session)
        session.commit()

        n_meets = tot_p = tot_i = 0
        for url in meet_urls:
            try:
                parsed = tfrrs.parse_meet(http.get(url), known_teams=known)
            except Exception as exc:  # noqa: BLE001
                log.warning("meet fetch/parse failed %s: %s", url, exc)
                continue
            if kinds and parsed["meet_kind"] not in kinds:
                continue
            if parsed["season"] not in seasons:
                continue

            placements = [p for p in parsed["team_placements"] if p.gender]
            tot_p += loaders.load_team_placements(session, placements, dedup=True)
            if not args.no_individuals:
                inds = [r for r in parsed["individual_results"] if r.gender]
                tot_i += loaders.load_results(session, inds, dedup=True)
            session.commit()
            n_meets += 1
            log.info("[%s %s] %s: +%d placements, +%d individuals",
                     parsed["season"], parsed["meet_kind"],
                     parsed["meet_name"][:45], len(placements),
                     0 if args.no_individuals else len(parsed["individual_results"]))

        log.info("Done. meets=%d, placements=%d, individuals=%d",
                 n_meets, tot_p, tot_i)


if __name__ == "__main__":
    main()
