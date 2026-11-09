"""Sign in with Google (OpenID Connect, authorization-code flow with PKCE).

1. /google/start creates a random `state` and PKCE verifier, keeps them in a short-lived
   httpOnly cookie, and redirects to Google.
2. Google redirects back to /google/callback with `code` and `state`. The state must match the
   cookie (stops login CSRF); the code is exchanged server-to-server over TLS, with the verifier.
3. The ID token comes straight from Google's token endpoint over TLS, which OpenID Connect Core
   3.1.3.7 accepts in place of a signature check; issuer, audience and expiry are still checked.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
STATE_COOKIE = "nyayasim_oauth"


class GoogleError(Exception):
    pass


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str


def redirect_uri() -> str:
    return settings.public_url.rstrip("/") + "/api/v1/auth/google/callback"


def new_flow() -> tuple[str, str, str]:
    """(state, code_verifier, code_challenge)."""
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return state, verifier, challenge


def authorize_url(state: str, challenge: str) -> str:
    return (
        AUTH_URL
        + "?"
        + urlencode(
            {
                "client_id": settings.google_client_id,
                "redirect_uri": redirect_uri(),
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
    )


def _claims(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as e:
        raise GoogleError("Google returned an unreadable sign-in token.") from e


def check_claims(claims: dict) -> GoogleIdentity:
    if claims.get("iss") not in ISSUERS:
        raise GoogleError("The sign-in token was not issued by Google.")
    aud = claims.get("aud")
    if aud != settings.google_client_id and not (isinstance(aud, list) and settings.google_client_id in aud):
        raise GoogleError("The sign-in token was issued for a different app.")
    if float(claims.get("exp", 0)) < time.time() - 60:
        raise GoogleError("The sign-in token has expired. Please try again.")
    email = str(claims.get("email") or "").strip().lower()
    if not claims.get("sub") or not email:
        raise GoogleError("Google did not share an email address for this account.")
    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=email,
        email_verified=claims.get("email_verified") in (True, "true"),
        name=str(claims.get("name") or "")[:120],
    )


def exchange_code(code: str, verifier: str) -> GoogleIdentity:
    secret = settings.google_client_secret.get_secret_value() if settings.google_client_secret else ""
    try:
        r = httpx.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": secret,
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
            timeout=15,
        )
    except httpx.HTTPError as e:
        raise GoogleError("Could not reach Google. Please try again.") from e
    if r.status_code != 200:
        raise GoogleError("Google did not accept the sign-in. Please try again.")
    id_token = r.json().get("id_token")
    if not id_token:
        raise GoogleError("Google did not return a sign-in token.")
    return check_claims(_claims(id_token))
