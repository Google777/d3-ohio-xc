"""Polite HTTP client: on-disk cache + rate limiting + retry/backoff.

Design goals:
- Never hammer TFRRS. A single shared session enforces a minimum delay
  between *live* (uncached) requests.
- Cache every fetched page to disk keyed by URL hash, so re-parsing during
  development costs zero network.
- Fail loudly but politely (respect 429/503 with backoff).
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from d3xc import config

log = logging.getLogger(__name__)


class RetryableStatus(Exception):
    """Raised for transient HTTP statuses so tenacity retries."""


class PoliteSession:
    """A thin wrapper over requests.Session with caching + throttling."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        delay: float = config.REQUEST_DELAY_SECONDS,
        user_agent: str = config.USER_AGENT,
    ) -> None:
        self.cache_dir = cache_dir or config.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": user_agent})
        self._last_request_ts = 0.0
        self._lock = threading.Lock()

    # -- cache helpers -----------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.html"

    def cached(self, url: str) -> str | None:
        p = self._cache_path(url)
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace")
        return None

    # -- throttle ----------------------------------------------------------
    def _throttle(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_request_ts
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self._last_request_ts = time.monotonic()

    # -- fetch -------------------------------------------------------------
    @retry(
        retry=retry_if_exception_type(RetryableStatus),
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def _live_get(self, url: str) -> str:
        self._throttle()
        log.info("GET %s", url)
        resp = self._session.get(url, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code in (429, 500, 502, 503, 504):
            raise RetryableStatus(f"{resp.status_code} for {url}")
        resp.raise_for_status()
        return resp.text

    def get(self, url: str, use_cache: bool = True) -> str:
        """Return page HTML, using the disk cache when available."""
        if use_cache:
            hit = self.cached(url)
            if hit is not None:
                log.debug("cache hit %s", url)
                return hit
        html = self._live_get(url)
        self._cache_path(url).write_text(html, encoding="utf-8")
        return html


# module-level default session for convenience
_default: PoliteSession | None = None


def default_session() -> PoliteSession:
    global _default
    if _default is None:
        _default = PoliteSession()
    return _default
