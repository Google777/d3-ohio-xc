"""Check which team slugs in teams.yaml actually resolve on TFRRS.

Because TFRRS slugs are guessed best-effort, this probes each team's men's page
and reports whether it looks like a real roster page (contains /athletes/ links).
Uses the polite cached session, so it is safe to re-run.

    python scripts/resolve_slugs.py
"""
from __future__ import annotations

import logging

import _bootstrap  # noqa: F401

from d3xc import config
from d3xc.scrape import tfrrs
from d3xc.scrape.http import default_session

logging.basicConfig(level=logging.WARNING)


def main():
    http = default_session()
    ok, bad = [], []
    for team in config.load_teams():
        url = tfrrs.team_url(team.tfrrs_slug, "men")
        try:
            html = http.get(url)
            links = tfrrs.discover_athlete_links(html)
            (ok if links else bad).append((team.name, len(links), url))
        except Exception as exc:  # noqa: BLE001
            bad.append((team.name, f"ERROR {exc}", url))

    print("\n=== RESOLVED (has athlete links) ===")
    for name, n, url in ok:
        print(f"  {name:24s} {n:4d} athletes  {url}")
    print("\n=== UNRESOLVED (fix slug in config/teams.yaml) ===")
    for name, n, url in bad:
        print(f"  {name:24s} {n}  {url}")
    print(f"\n{len(ok)}/{len(ok)+len(bad)} team slugs resolved.")


if __name__ == "__main__":
    main()
