"""Polite HTTP fetcher. Every request — success or failure — is written to fetch_log.

Rules (from the data gate): sequential requests, a minimum delay between them, an
identifying user agent, no login, no CAPTCHA solving.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.models import FetchLog

USER_AGENT = "NyayaSim research crawler (slow, sequential; contact via project maintainer)"


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    body: bytes
    sha256: str


class FetchError(RuntimeError):
    pass


class PoliteFetcher:
    def __init__(self, engine: Engine, min_delay_s: float = 2.5, timeout_s: float = 60.0) -> None:
        self.engine = engine
        self.min_delay_s = min_delay_s
        self.timeout_s = timeout_s
        self._last_request_at: float | None = None

    def _wait_turn(self) -> None:
        if self._last_request_at is not None:
            remaining = self.min_delay_s - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def get(self, url: str) -> FetchResult:
        """Fetch ``url``. Logs the attempt, then returns the body or raises FetchError."""
        self._wait_turn()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = resp.read()
                status = resp.status
        except urllib.error.HTTPError as e:
            self._log(url, http_status=e.code, error=f"HTTP {e.code}: {e.reason}")
            raise FetchError(f"{url}: HTTP {e.code}") from e
        except Exception as e:  # network errors, timeouts
            self._log(url, error=f"{type(e).__name__}: {e}"[:500])
            raise FetchError(f"{url}: {type(e).__name__}: {e}") from e

        digest = hashlib.sha256(body).hexdigest()
        self._log(url, http_status=status, size=len(body), sha256=digest)
        return FetchResult(url=url, status=status, body=body, sha256=digest)

    def _log(
        self,
        url: str,
        http_status: int | None = None,
        size: int | None = None,
        sha256: str | None = None,
        error: str | None = None,
    ) -> None:
        # Own short session, committed at once: the log survives even if the caller's work is
        # rolled back, and logging never commits the caller's half-finished transaction.
        with Session(self.engine) as s:
            s.add(FetchLog(url=url, http_status=http_status, bytes=size, sha256=sha256, error=error))
            s.commit()
