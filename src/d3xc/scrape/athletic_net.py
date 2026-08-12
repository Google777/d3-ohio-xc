"""High-school PR linkage (best-effort).

TFRRS is college-only. High-school marks live on Athletic.net / MileSplit, which
have no open API and require name + grad-year matching to a college athlete.
This module provides:
  * a fuzzy matcher (rapidfuzz) that scores a college athlete against candidate
    HS athletes and returns a confidence,
  * a search/parse stub for Athletic.net that is intentionally conservative.

We DO NOT ship an aggressive Athletic.net crawler here: their terms are stricter
and matching is error-prone. The recommended path is to curate a small
`config/hs_marks.csv` and let this module attach confidence scores, upgrading to
live search only where you have explicit permission.
"""
from __future__ import annotations

import logging
from typing import Optional

from rapidfuzz import fuzz

from d3xc.scrape.records import HSMark

log = logging.getLogger(__name__)


def name_similarity(a: str, b: str) -> float:
    """0..1 similarity between two athlete names (order-insensitive)."""
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(a.lower(), b.lower()) / 100.0


def link_hs_mark(
    college_name: str,
    candidate_name: str,
    *,
    college_team: str,
    gender: str,
    event: str,
    mark_seconds: Optional[float],
    hs_grad_year: Optional[int],
    source: str,
    grad_year_hint: Optional[int] = None,
) -> HSMark:
    """Build an HSMark with a confidence blending name + grad-year agreement."""
    conf = name_similarity(college_name, candidate_name)
    if grad_year_hint and hs_grad_year:
        # penalize grad-year mismatch (each year off costs 0.1, capped)
        conf -= min(0.5, 0.1 * abs(grad_year_hint - hs_grad_year))
    conf = max(0.0, min(1.0, conf))
    return HSMark(
        athlete_name=college_name,
        college_team=college_team,
        gender=gender,
        event=event,
        mark_seconds=mark_seconds,
        hs_grad_year=hs_grad_year,
        source=source,
        match_confidence=round(conf, 3),
    )


def search_athletic_net(name: str, state: str = "OH") -> list[dict]:
    """Placeholder for Athletic.net athlete search.

    Not implemented as a live crawler by default (see module docstring). Returns
    an empty list so the pipeline degrades gracefully to curated HS data.
    """
    log.info("Athletic.net live search is disabled; using curated HS data only.")
    return []
