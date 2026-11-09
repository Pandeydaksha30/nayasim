"""Accounts: sign-up, email verification, sign-in, lockout, password reset, Google sign-in,
per-user case isolation, CSRF origin check, account deletion."""

from __future__ import annotations

import re
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import auth as auth_api
from app.auth import google
from app.auth.security import limiter, password_problem, verify_password
from app.config import settings
from app.db.models import Case, User
from app.db.session import get_session
from app.main import app

ORIGIN = {"Origin": "http://localhost:3100"}
PW = "a long and private passphrase"


@pytest.fixture
def env(db_engine, monkeypatch):
    with db_engine.begin() as c:
        c.execute(text("TRUNCATE users, cases, auth_events RESTART IDENTITY CASCADE"))
    limiter.reset()
    sent: list[dict] = []

    def fake_send(to, subject, body, link=None):
        sent.append({"to": to, "subject": subject, "body": body, "link": link})

    monkeypatch.setattr(auth_api, "send_mail", fake_send)
    monkeypatch.setattr(settings, "public_url", "http://localhost:3100")

    def session_override():
        with Session(db_engine) as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    app.dependency_overrides[get_session] = session_override
    yield db_engine, sent
    app.dependency_overrides.clear()
    limiter.reset()


def client() -> TestClient:
    return TestClient(app, headers=ORIGIN)


def token_from(mail: dict) -> str:
    return re.search(r"token=([\w\-%]+)", mail["link"]).group(1)


def signup_and_verify(c: TestClient, sent, email="asha@example.com", name="Asha"):
    r = c.post(
        "/api/v1/auth/signup", json={"name": name, "email": email, "password": PW, "accept_terms": True}
    )
    assert r.status_code == 202, r.text
    r = c.post("/api/v1/auth/verify-email", json={"token": token_from(sent[-1])})
    assert r.status_code == 200, r.text
    return r.json()


# ── Unit ──


def test_password_rules():
    assert password_problem("short") is not None
    assert password_problem("1234567890") is not None  # common
    assert password_problem("aaaaaaaaaaaa") is not None  # too few distinct characters
    assert password_problem("asha.sharma-secret", "asha.sharma@example.com") is not None
    assert password_problem(PW, "asha@example.com") is None


def test_unknown_account_password_check_is_false():
    assert verify_password(None, "timing-equaliser-not-a-real-password") is False


def test_next_redirect_only_allows_local_paths():
    assert auth_api._safe_next("/cases/1") == "/cases/1"
    for bad in ["https://evil.example", "//evil.example", "/\\evil.example", None, ""]:
        assert auth_api._safe_next(bad) == "/"


def test_google_claims_are_checked(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-1")
    good = {
        "iss": "https://accounts.google.com",
        "aud": "client-1",
        "exp": time.time() + 60,
        "sub": "123",
        "email": "A@Example.com",
        "email_verified": True,
        "name": "A",
    }
    ident = google.check_claims(good)
    assert ident.email == "a@example.com" and ident.email_verified
    for bad in [{"iss": "https://evil"}, {"aud": "other"}, {"exp": time.time() - 3600}, {"email": ""}]:
        with pytest.raises(google.GoogleError):
            google.check_claims({**good, **bad})


# ── Sign-up, verification, sign-in ──


def test_signup_verify_login_logout(env):
    engine, sent = env
    c = client()
    user = signup_and_verify(c, sent)
    assert user["email"] == "asha@example.com" and user["email_verified"]
    cookie = c.cookies.get("nyayasim_session")
    assert cookie
    assert c.get("/api/v1/auth/me").json()["name"] == "Asha"
    # The cookie is httpOnly + SameSite=Lax.
    c2 = client()
    r = c2.post("/api/v1/auth/login", json={"email": "ASHA@example.com", "password": PW})
    assert r.status_code == 200
    header = r.headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header
    # The raw token is never stored.
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM user_sessions WHERE token_hash = :t"), {"t": cookie}
            ).scalar()
            == 0
        )
    assert c2.post("/api/v1/auth/logout").status_code == 200
    assert c2.get("/api/v1/auth/me").status_code == 401


def test_verify_link_is_single_use(env):
    _, sent = env
    c = client()
    c.post(
        "/api/v1/auth/signup",
        json={"name": "A", "email": "a@example.com", "password": PW, "accept_terms": True},
    )
    tok = token_from(sent[-1])
    assert c.post("/api/v1/auth/verify-email", json={"token": tok}).status_code == 200
    assert client().post("/api/v1/auth/verify-email", json={"token": tok}).status_code == 400


def test_unverified_cannot_sign_in(env):
    _, sent = env
    c = client()
    c.post(
        "/api/v1/auth/signup",
        json={"name": "A", "email": "a@example.com", "password": PW, "accept_terms": True},
    )
    r = c.post("/api/v1/auth/login", json={"email": "a@example.com", "password": PW})
    assert r.status_code == 403 and "confirm your email" in r.json()["detail"]


def test_terms_and_weak_password_rejected(env):
    c = client()
    base = {"name": "A", "email": "a@example.com", "password": PW, "accept_terms": True}
    assert c.post("/api/v1/auth/signup", json={**base, "accept_terms": False}).status_code == 422
    assert c.post("/api/v1/auth/signup", json={**base, "password": "1234567890"}).status_code == 422


def test_signup_does_not_reveal_existing_accounts(env):
    _, sent = env
    c = client()
    signup_and_verify(c, sent)
    r = client().post(
        "/api/v1/auth/signup",
        json={"name": "X", "email": "asha@example.com", "password": PW + "x", "accept_terms": True},
    )
    assert r.status_code == 202
    assert sent[-1]["to"] == "asha@example.com" and "already has an account" in sent[-1]["body"]


def test_wrong_password_and_unknown_email_look_the_same(env):
    _, sent = env
    signup_and_verify(client(), sent)
    a = client().post(
        "/api/v1/auth/login", json={"email": "asha@example.com", "password": "wrong password!!"}
    )
    b = client().post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong password!!"}
    )
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_lockout_after_repeated_wrong_passwords(env):
    _, sent = env
    signup_and_verify(client(), sent)
    for _ in range(8):
        client().post(
            "/api/v1/auth/login", json={"email": "asha@example.com", "password": "wrong password!!"}
        )
    r = client().post("/api/v1/auth/login", json={"email": "asha@example.com", "password": PW})
    assert r.status_code == 423


def test_login_rate_limited(env):
    for _ in range(10):
        client().post("/api/v1/auth/login", json={"email": "x@example.com", "password": "whatever123"})
    assert (
        client()
        .post("/api/v1/auth/login", json={"email": "x@example.com", "password": "whatever123"})
        .status_code
        == 429
    )


# ── Password reset and change ──


def test_reset_password_signs_out_everywhere(env):
    _, sent = env
    c = client()
    signup_and_verify(c, sent)
    assert c.get("/api/v1/auth/me").status_code == 200
    r = client().post("/api/v1/auth/forgot-password", json={"email": "asha@example.com"})
    assert r.status_code == 202
    tok = token_from(sent[-1])
    assert (
        client().post("/api/v1/auth/reset-password", json={"token": tok, "password": "short"}).status_code
        == 422
    )
    new_pw = "a different long passphrase"
    assert (
        client().post("/api/v1/auth/reset-password", json={"token": tok, "password": new_pw}).status_code
        == 200
    )
    assert c.get("/api/v1/auth/me").status_code == 401  # old session ended
    assert (
        client().post("/api/v1/auth/reset-password", json={"token": tok, "password": new_pw}).status_code
        == 400
    )
    assert (
        client()
        .post("/api/v1/auth/login", json={"email": "asha@example.com", "password": new_pw})
        .status_code
        == 200
    )


def test_forgot_password_same_answer_for_unknown_email(env):
    _, sent = env
    r = client().post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 202 and sent == []


def test_change_password_needs_current(env):
    _, sent = env
    c = client()
    signup_and_verify(c, sent)
    bad = c.post(
        "/api/v1/auth/change-password",
        json={"current_password": "nope nope nope", "new_password": "another long passphrase"},
    )
    assert bad.status_code == 403
    ok = c.post(
        "/api/v1/auth/change-password",
        json={"current_password": PW, "new_password": "another long passphrase"},
    )
    assert ok.status_code == 200
    assert c.get("/api/v1/auth/me").status_code == 200  # this device stays signed in


# ── Cases belong to their owner ──


def test_cases_are_private_to_their_owner(env):
    engine, sent = env
    a, b = client(), client()
    signup_and_verify(a, sent, "a@example.com")
    signup_and_verify(b, sent, "b@example.com")
    case = a.post("/api/v1/cases", json={"title": "A v. Builder"}).json()
    assert [c["id"] for c in a.get("/api/v1/cases").json()] == [case["id"]]
    assert b.get("/api/v1/cases").json() == []
    assert b.get(f"/api/v1/cases/{case['id']}").status_code == 404
    assert b.put(f"/api/v1/cases/{case['id']}/answers/x", json={"answer": "y"}).status_code == 404
    assert b.get(f"/api/v1/cases/{case['id']}/hearing").status_code == 404
    assert client().get("/api/v1/cases").status_code == 401


def test_shared_demo_case_is_read_only(env):
    engine, sent = env
    with Session(engine) as s:
        demo = Case(title="Example", claim_type="delayed_possession", is_demo=True)
        s.add(demo)
        s.commit()
        demo_id = demo.id
    c = client()
    signup_and_verify(c, sent)
    assert c.get(f"/api/v1/cases/{demo_id}").status_code == 200
    r = c.post(
        f"/api/v1/cases/{demo_id}/documents",
        data={"kind": "agreement"},
        files={"file": ("a.pdf", b"%PDF-1.4")},
    )
    assert r.status_code == 403


# ── CSRF ──


def test_cross_site_requests_are_blocked(env):
    _, sent = env
    c = client()
    signup_and_verify(c, sent)
    evil = {"Origin": "https://evil.example"}
    assert c.post("/api/v1/cases", json={"title": "x"}, headers=evil).status_code == 403
    assert c.post("/api/v1/cases", json={"title": "x"}, headers={"Origin": "null"}).status_code == 403
    assert c.post("/api/v1/cases", json={"title": "x"}).status_code == 201
    r = c.get("/api/v1/auth/me")
    assert r.headers["x-frame-options"] == "DENY" and r.headers["cache-control"] == "no-store"


# ── Google ──


def _google(monkeypatch, ident: google.GoogleIdentity):
    monkeypatch.setattr(settings, "google_client_id", "client-1")
    monkeypatch.setattr(settings, "google_client_secret", "secret")
    monkeypatch.setattr(google, "exchange_code", lambda code, verifier: ident)


def _google_login(c: TestClient, next_path="/cases/new"):
    r = c.get(f"/api/v1/auth/google/start?next={next_path}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith(google.AUTH_URL)
    state = re.search(r"state=([^&]+)", r.headers["location"]).group(1)
    assert "code_challenge_method=S256" in r.headers["location"]
    return c.get(f"/api/v1/auth/google/callback?code=abc&state={state}", follow_redirects=False)


def test_google_sign_up_and_wrong_state(env, monkeypatch):
    _google(monkeypatch, google.GoogleIdentity("sub-1", "g@example.com", True, "Gita"))
    c = client()
    r = _google_login(c)
    assert r.status_code == 302 and r.headers["location"] == "/cases/new"
    me = c.get("/api/v1/auth/me").json()
    assert me["email"] == "g@example.com" and me["google_linked"] and not me["has_password"]
    # A callback whose state does not match the browser's cookie is refused (login CSRF).
    other = client()
    r = other.get("/api/v1/auth/google/callback?code=abc&state=forged", follow_redirects=False)
    assert r.headers["location"].startswith("/login?error=")
    assert other.get("/api/v1/auth/me").status_code == 401


def test_google_takes_over_unverified_squatter_account(env, monkeypatch):
    engine, sent = env
    attacker = client()
    attacker.post(
        "/api/v1/auth/signup",
        json={"name": "X", "email": "v@example.com", "password": PW, "accept_terms": True},
    )
    _google(monkeypatch, google.GoogleIdentity("sub-v", "v@example.com", True, "Victim"))
    victim = client()
    _google_login(victim)
    with Session(engine) as s:
        u = s.query(User).filter_by(email="v@example.com").one()
        assert u.password_hash is None and u.google_sub == "sub-v" and u.email_verified
    assert (
        attacker.post("/api/v1/auth/login", json={"email": "v@example.com", "password": PW}).status_code
        == 401
    )


def test_google_hidden_when_not_configured(env, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    assert client().get("/api/v1/auth/config").json()["google"] is False
    assert client().get("/api/v1/auth/google/start", follow_redirects=False).status_code == 404


# ── Account deletion ──


def test_delete_account_removes_cases(env):
    engine, sent = env
    c = client()
    signup_and_verify(c, sent)
    case_id = c.post("/api/v1/cases", json={"title": "Mine"}).json()["id"]
    assert c.request("DELETE", "/api/v1/auth/me", json={"password": PW, "confirm": "nope"}).status_code == 422
    assert (
        c.request(
            "DELETE", "/api/v1/auth/me", json={"password": "wrong pw here", "confirm": "DELETE"}
        ).status_code
        == 403
    )
    assert (
        c.request("DELETE", "/api/v1/auth/me", json={"password": PW, "confirm": "DELETE"}).status_code == 200
    )
    with Session(engine) as s:
        assert s.get(Case, uuid.UUID(case_id)) is None
        assert s.query(User).count() == 0
        events = [e for (e,) in s.execute(text("SELECT event FROM auth_events ORDER BY id"))]
    assert "account_deleted" in events


def test_housekeeping_purges_old_records(env):
    from datetime import UTC, datetime, timedelta

    from app.auth.service import purge_expired
    from app.db.models import AuthEvent, AuthToken, UserSession

    engine, sent = env
    signup_and_verify(client(), sent)
    old = datetime.now(UTC) - timedelta(days=400)
    with Session(engine) as s:
        uid = s.query(User).one().id
        s.add(UserSession(token_hash="x" * 64, user_id=uid, expires_at=old))
        s.add(AuthToken(token_hash="y" * 64, user_id=uid, purpose="reset_password", expires_at=old))
        s.add(AuthEvent(user_id=uid, event="login", at=old))
        s.commit()
        counts = purge_expired(s)
        s.commit()
        assert counts["sessions"] == 1 and counts["events"] == 1 and counts["tokens"] >= 1
        assert s.query(UserSession).count() == 1  # the live session from sign-up stays


def test_users_cannot_mark_their_case_as_demo(env):
    """Privacy: a demo case may go to a data-retaining model, so users must not be able to choose it."""
    _, sent = env
    c = client()
    signup_and_verify(c, sent)
    r = c.post("/api/v1/cases", json={"title": "Real papers", "is_demo": True})
    assert r.status_code == 403
    assert c.get("/api/v1/cases").json() == []
    assert client().get("/api/v1/auth/config").json()["demo_cases"] is False
