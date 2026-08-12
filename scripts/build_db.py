"""Initialize the DB schema and load config-only data (teams + coaches)."""
from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401

from d3xc.store import loaders
from d3xc.store.db import get_sessionmaker, init_db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true", help="drop & recreate all tables")
    args = ap.parse_args()

    engine = init_db(drop=args.fresh)
    Session = get_sessionmaker(engine)
    with Session() as session:
        teams = loaders.upsert_teams(session)
        session.commit()
        coaches = loaders.load_coaches_csv(session)
        session.commit()
    print(f"DB ready: {len(teams)} teams, {coaches} coach tenures.")


if __name__ == "__main__":
    main()
