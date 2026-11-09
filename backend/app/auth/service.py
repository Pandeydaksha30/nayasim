"""Sessions, one-time email tokens and the audit log."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.auth.security import new_token, token_hash
from app.config import settings
from app.db.models import AuthEvent, AuthToken, User, UserSession

SESSION_COOKIE = "nyayasim_session"
# A session's last_seen_at is written at most this often, so reads do not all become writes.
_TOUCH_EVERY = timedelta(minutes=5)
TOKEN_TTL = {"verify_email": timedelta(hours=24), "reset_password": timedelta(hours=1)}
LOCK_AFTER, LOCK_FOR = 8, timedelta(minutes=15)


def now() -> datetime:
    return datetime.now(UTC)


def client_ip(request: Request) -> str:
    # uvicorn --proxy-headers already resolves X-Forwarded-For from the trusted proxy.
    return request.client.host if request.client else "unknown"


def _ua(request: Request) -> str:
    return (request.headers.get("user-agent") or "")[:300]


def log_event(
    s: Session, request: Request, event: str, user: User | None = None, email: str | None = None
) -> None:
    s.add(
        AuthEvent(
            user_id=user.id if user else None,
            email=(user.email if user else email),
            event=event,
            ip=client_ip(request),
            user_agent=_ua(request),
        )
    )


# ── Sessions ──


def start_session(s: Session, request: Request, response: Response, user: User) -> None:
    token = new_token()
    s.add(
        UserSession(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=now() + timedelta(days=settings.session_days),
            ip=client_ip(request),
            user_agent=_ua(request),
        )
    )
    user.last_login_at = now()
    user.failed_logins = 0
    user.locked_until = None
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,  # page scripts cannot read it
        secure=settings.cookie_secure,
        samesite="lax",  # not sent on cross-site form posts or fetches
        path="/",
    )


def clear_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax"
    )


def user_for_token(s: Session, token: str | None) -> User | None:
    if not token or len(token) > 200:
        return None
    sess = s.get(UserSession, token_hash(token))
    if sess is None:
        return None
    t = now()
    if sess.expires_at <= t:
        s.delete(sess)
        return None
    if t - sess.last_seen_at > _TOUCH_EVERY:
        sess.last_seen_at = t
    return s.get(User, sess.user_id)


def end_session(s: Session, token: str | None) -> None:
    if token:
        s.execute(delete(UserSession).where(UserSession.token_hash == token_hash(token)))


def end_all_sessions(s: Session, user_id: uuid.UUID, keep_token: str | None = None) -> int:
    q = delete(UserSession).where(UserSession.user_id == user_id)
    if keep_token:
        q = q.where(UserSession.token_hash != token_hash(keep_token))
    return s.execute(q).rowcount or 0


# ── One-time email tokens ──


def issue_token(s: Session, user: User, purpose: str) -> str:
    # Older unused links for the same purpose stop working once a new one is sent.
    s.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
        .values(used_at=now())
    )
    token = new_token()
    s.add(
        AuthToken(
            token_hash=token_hash(token),
            user_id=user.id,
            purpose=purpose,
            expires_at=now() + TOKEN_TTL[purpose],
        )
    )
    return token


def consume_token(s: Session, token: str, purpose: str) -> User | None:
    """The token's user, marking the token used; None if unknown, used, expired or wrong purpose."""
    if not token or len(token) > 200:
        return None
    row = s.scalar(select(AuthToken).where(AuthToken.token_hash == token_hash(token)).with_for_update())
    if row is None or row.purpose != purpose or row.used_at is not None or row.expires_at <= now():
        return None
    row.used_at = now()
    return s.get(User, row.user_id)


# ── Lockout ──


def is_locked(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > now()


def record_failed_login(user: User) -> None:
    user.failed_logins += 1
    if user.failed_logins >= LOCK_AFTER:
        user.locked_until = now() + LOCK_FOR
        user.failed_logins = 0


# ── Housekeeping ──

EVENT_RETENTION = timedelta(days=365)  # stated in the Privacy Policy (frontend/app/privacy)


def purge_expired(s: Session) -> dict[str, int]:
    """Delete expired sessions, used or expired email tokens, and audit events older than a year."""
    t = now()
    return {
        "sessions": s.execute(delete(UserSession).where(UserSession.expires_at <= t)).rowcount or 0,
        "tokens": s.execute(
            delete(AuthToken).where((AuthToken.expires_at <= t) | (AuthToken.used_at.is_not(None)))
        ).rowcount
        or 0,
        "events": s.execute(delete(AuthEvent).where(AuthEvent.at <= t - EVENT_RETENTION)).rowcount or 0,
    }
