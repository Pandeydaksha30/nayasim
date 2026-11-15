"""Per-user rate limits for routes that cost model quota, OCR time or CPU.

Sign-in routes have their own limits in app/api/auth.py. These use the same in-process limiter
(app/auth/security.py): one API process per server; several servers would need a shared store.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.auth.deps import CurrentUser
from app.auth.security import limiter
from app.auth.service import client_ip


def _too_many(window_s: float) -> HTTPException:
    minutes = max(1, round(window_s / 60))
    return HTTPException(
        429, f"Too many requests. Please wait and try again (the limit resets within {minutes} min)."
    )


def user_limit(name: str, limit: int, window_s: float):
    """Route dependency: at most `limit` calls per `window_s` seconds for each signed-in user."""

    def check(user: CurrentUser) -> None:
        if not limiter.hit(f"{name}:{user.id}", limit, window_s):
            raise _too_many(window_s)

    return Depends(check)


def ip_limit(name: str, limit: int, window_s: float):
    """Route dependency for public routes: the limit is per visitor address."""

    def check(request: Request) -> None:
        if not limiter.hit(f"{name}:{client_ip(request)}", limit, window_s):
            raise _too_many(window_s)

    return Depends(check)
