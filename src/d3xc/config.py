"""Central configuration: paths, seasons, scraping etiquette, and team loading."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

# --- paths ---
PKG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PKG_DIR.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = RAW_DIR / "http_cache"
PROCESSED_DIR = DATA_DIR / "processed"
DB_PATH = DATA_DIR / "d3xc.db"

TEAMS_YAML = CONFIG_DIR / "teams.yaml"
COACHES_CSV = CONFIG_DIR / "coaches.csv"
HS_MARKS_CSV = CONFIG_DIR / "hs_marks.csv"

# --- analysis window: last 10 completed XC seasons (as of 2026) ---
FIRST_SEASON = 2016
LAST_SEASON = 2025
SEASONS = list(range(FIRST_SEASON, LAST_SEASON + 1))

# --- scraping etiquette ---
TFRRS_BASE = "https://www.tfrrs.org"
USER_AGENT = (
    "d3-ohio-xc-research/0.1 (educational, non-commercial; polite crawler)"
)
REQUEST_DELAY_SECONDS = 3.0   # minimum gap between live requests
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

# XC race distances (meters) used to normalize marks across meets
XC_DISTANCES_M = {"men": 8000, "women": 6000}


@dataclasses.dataclass(frozen=True)
class Team:
    name: str
    conference: str
    tfrrs_slug: str
    verified: bool = False


def load_teams() -> list[Team]:
    """Load the Ohio D3 team roster from config/teams.yaml."""
    with open(TEAMS_YAML, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return [
        Team(
            name=t["name"],
            conference=t["conference"],
            tfrrs_slug=t["tfrrs_slug"],
            verified=bool(t.get("verified", False)),
        )
        for t in data["teams"]
    ]


def load_conferences() -> dict[str, str]:
    with open(TEAMS_YAML, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("conferences", {})


def ensure_dirs() -> None:
    for d in (DATA_DIR, RAW_DIR, CACHE_DIR, PROCESSED_DIR):
        d.mkdir(parents=True, exist_ok=True)
