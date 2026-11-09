"""Security primitives: password hashing and rules, random tokens, rate limiting.

- Passwords: Argon2id (argon2-cffi defaults, the OWASP-recommended algorithm). Hashes are
  re-computed on login when the parameters change.
- Tokens (session cookies, email links): 32 random bytes; only their SHA-256 is stored.
- Rate limits: in-process sliding window. The API runs as one process per server; a multi-server
  setup would need a shared store (Redis) instead.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

# A stand-in hash, verified against when the account does not exist, so a wrong email takes as
# long as a wrong password (no timing difference reveals which emails have accounts).
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")

PASSWORD_MIN, PASSWORD_MAX = 10, 128
# The most common passwords that pass the length rule. A full breached-password check would need
# an outside service; this catches the obvious ones without sending anything anywhere.
_COMMON = {
    "1234567890",
    "12345678910",
    "123456789012",
    "0123456789",
    "1111111111",
    "0000000000",
    "qwertyuiop",
    "password12",
    "password123",
    "password1234",
    "iloveyou12",
    "qwerty1234",
    "abcdefghij",
    "abc1234567",
    "passw0rd12",
    "welcome123",
    "admin12345",
    "letmein123",
    "1q2w3e4r5t",
    "qwerty12345",
    "asdfghjkl1",
    "zaq12wsxcde",
    "india12345",
    "nyayasim123",
}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    """True if `password` matches. Always spends the same time, even with no stored hash."""
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def password_problem(password: str, email: str = "") -> str | None:
    """Why a new password is not acceptable, or None if it is."""
    if len(password) < PASSWORD_MIN:
        return f"Use at least {PASSWORD_MIN} characters."
    if len(password) > PASSWORD_MAX:
        return f"Use at most {PASSWORD_MAX} characters."
    low = password.lower()
    if low in _COMMON or len(set(password)) < 4:
        return "This password is too easy to guess. Try a short sentence or a mix of words."
    local = email.split("@")[0].lower()
    if local and len(local) >= 4 and local in low:
        return "Don't include your email address in your password."
    return None


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class RateLimiter:
    """At most `limit` events per `window_s` seconds for each key."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_s: float) -> bool:
        """Record one event; False if the key is over its limit (the event is then not recorded)."""
        now = time.monotonic()
        with self._lock:
            q = self._events[key]
            while q and q[0] <= now - window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            if len(self._events) > 50_000:  # bound memory: drop keys with no recent events
                for k in [k for k, v in self._events.items() if not v]:
                    del self._events[k]
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


limiter = RateLimiter()
