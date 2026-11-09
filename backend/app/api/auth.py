"""Accounts API: sign up, verify email, sign in (password or Google), reset password, manage
account, sign out, delete account.

Security choices:
- Session in an httpOnly, SameSite=Lax cookie (Secure in production); state-changing requests
  also need a matching Origin header (app/middleware.py).
- Same answer and same timing whether or not an email has an account, for sign-in, sign-up and
  "forgot password" (no account discovery).
- Rate limits per IP and per email; 8 wrong passwords lock the account for 15 minutes.
- Email links are single use and expire (24 h verify, 1 h reset). A reset signs out every device.
"""

from __future__ import annotations

import shutil
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import google
from app.auth.deps import CurrentUser
from app.auth.mailer import MailError, send_mail
from app.auth.security import hash_password, limiter, needs_rehash, password_problem, verify_password
from app.auth.service import (
    SESSION_COOKIE,
    clear_cookie,
    client_ip,
    consume_token,
    end_all_sessions,
    end_session,
    is_locked,
    issue_token,
    log_event,
    record_failed_login,
    start_session,
)
from app.buyer import documents as documents_mod
from app.config import settings
from app.db.models import Case, User
from app.db.session import get_session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
SessionDep = Annotated[Session, Depends(get_session)]
TokenCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]

GENERIC_LOGIN_ERROR = "Email or password is incorrect."


def _limit(key: str, limit: int, window_s: float) -> None:
    if not limiter.hit(key, limit, window_s):
        raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")


def _norm(email: str) -> str:
    return email.strip().lower()


def _safe_next(path: str | None) -> str:
    """Only same-site relative paths, so a sign-in link cannot redirect to another site."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return path


# ── Models ──


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    email_verified: bool
    has_password: bool
    google_linked: bool
    created_at: str


def user_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        email=u.email,
        name=u.name,
        email_verified=u.email_verified,
        has_password=u.password_hash is not None,
        google_linked=u.google_sub is not None,
        created_at=u.created_at.isoformat(),
    )


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    accept_terms: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class EmailIn(BaseModel):
    email: EmailStr


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ChangePasswordIn(BaseModel):
    current_password: str | None = Field(None, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class DeleteIn(BaseModel):
    password: str | None = Field(None, max_length=200)
    confirm: str = Field(max_length=40)


class Message(BaseModel):
    message: str


# ── Email helpers ──


def _send_verify(s: Session, user: User) -> None:
    link = (
        f"{settings.public_url.rstrip('/')}/verify-email?token={quote(issue_token(s, user, 'verify_email'))}"
    )
    send_mail(
        user.email,
        "Confirm your email for NyayaSim",
        f"Hello {user.name or 'there'},\n\nConfirm your email address to finish setting up your NyayaSim "
        f"account:\n\n{link}\n\nThe link works once and expires in 24 hours. If you did not sign up, "
        "you can ignore this email.\n\n— NyayaSim",
        link,
    )


def _send_reset(s: Session, user: User) -> None:
    token = quote(issue_token(s, user, "reset_password"))
    link = f"{settings.public_url.rstrip('/')}/reset-password?token={token}"
    send_mail(
        user.email,
        "Reset your NyayaSim password",
        f"Hello {user.name or 'there'},\n\nSomeone (hopefully you) asked to reset the password for this "
        f"account. Choose a new password here:\n\n{link}\n\nThe link works once and expires in 1 hour. "
        "If you did not ask for this, ignore this email; your password stays the same.\n\n— NyayaSim",
        link,
    )


# ── Routes ──


@router.get("/config")
def auth_config() -> dict:
    """What the sign-in page should offer."""
    return {"google": settings.google_enabled, "email_delivery": "smtp" if settings.smtp_host else "outbox"}


@router.post("/signup", status_code=202, response_model=Message)
def signup(body: SignupIn, request: Request, s: SessionDep) -> Message:
    _limit(f"signup:{client_ip(request)}", 5, 600)
    if not body.accept_terms:
        raise HTTPException(422, "Please accept the Terms and Privacy Policy to create an account.")
    email = _norm(body.email)
    problem = password_problem(body.password, email)
    if problem:
        raise HTTPException(422, problem)

    existing = s.scalar(select(User).where(User.email == email))
    if existing is None:
        user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
        s.add(user)
        s.flush()
        log_event(s, request, "signup", user)
        try:
            _send_verify(s, user)
        except MailError as e:
            raise HTTPException(503, str(e)) from e
    else:
        # Same response as a new sign-up; the owner gets a notice instead (no account discovery).
        hash_password(body.password)  # equal timing
        log_event(s, request, "signup_existing_email", existing)
        try:
            send_mail(
                email,
                "Someone tried to sign up with your email",
                "Someone tried to create a NyayaSim account with this email address, which already has an "
                f"account. If that was you, sign in instead:\n\n{settings.public_url.rstrip('/')}/login\n\n"
                "Forgot your password? Use 'Forgot password' on the sign-in page.\n\n— NyayaSim",
            )
        except MailError:
            pass  # the response must not differ from a new sign-up; failure is logged by send_mail
    return Message(message="Check your inbox for a link to confirm your email address.")


@router.post("/verify-email", response_model=UserOut)
def verify_email(body: TokenIn, request: Request, response: Response, s: SessionDep) -> UserOut:
    _limit(f"verify:{client_ip(request)}", 20, 600)
    user = consume_token(s, body.token, "verify_email")
    if user is None:
        raise HTTPException(400, "This link is invalid or has expired. Sign in to get a new one.")
    user.email_verified = True
    log_event(s, request, "email_verified", user)
    start_session(s, request, response, user)
    return user_out(user)


@router.post("/resend-verification", status_code=202, response_model=Message)
def resend_verification(body: EmailIn, request: Request, s: SessionDep) -> Message:
    _limit(f"resend:{client_ip(request)}", 5, 900)
    _limit(f"resend-email:{_norm(body.email)}", 3, 900)
    user = s.scalar(select(User).where(User.email == _norm(body.email)))
    if user is not None and not user.email_verified and user.password_hash is not None:
        try:
            _send_verify(s, user)
        except MailError as e:
            raise HTTPException(503, str(e)) from e
    return Message(message="If that account is waiting for confirmation, a new link is on its way.")


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, s: SessionDep) -> UserOut:
    email = _norm(body.email)
    _limit(f"login:{client_ip(request)}", 20, 300)
    _limit(f"login-email:{email}", 10, 300)
    user = s.scalar(select(User).where(User.email == email).with_for_update())
    ok = verify_password(user.password_hash if user else None, body.password)
    if user is None:
        log_event(s, request, "login_failed_unknown", email=email)
        raise HTTPException(401, GENERIC_LOGIN_ERROR)
    if is_locked(user):
        log_event(s, request, "login_blocked_locked", user)
        raise HTTPException(
            423,
            "Too many wrong passwords. This account is locked for 15 minutes, "
            "or reset your password to unlock it now.",
        )
    if not ok:
        record_failed_login(user)
        log_event(s, request, "login_failed", user)
        # Commit the counter even though the request fails.
        s.commit()
        raise HTTPException(401, GENERIC_LOGIN_ERROR)
    if not user.email_verified:
        raise HTTPException(403, "Please confirm your email address first. We can send a new link.")
    if needs_rehash(user.password_hash):  # type: ignore[arg-type]
        user.password_hash = hash_password(body.password)
    start_session(s, request, response, user)
    log_event(s, request, "login", user)
    return user_out(user)


@router.post("/logout", response_model=Message)
def logout(response: Response, s: SessionDep, token: TokenCookie = None) -> Message:
    end_session(s, token)
    clear_cookie(response)
    return Message(message="Signed out.")


@router.post("/logout-all", response_model=Message)
def logout_all(user: CurrentUser, request: Request, response: Response, s: SessionDep) -> Message:
    n = end_all_sessions(s, user.id)
    log_event(s, request, "logout_all", user)
    clear_cookie(response)
    return Message(message=f"Signed out of {n} session(s) on all devices.")


@router.post("/forgot-password", status_code=202, response_model=Message)
def forgot_password(body: EmailIn, request: Request, s: SessionDep) -> Message:
    _limit(f"forgot:{client_ip(request)}", 5, 900)
    _limit(f"forgot-email:{_norm(body.email)}", 3, 900)
    user = s.scalar(select(User).where(User.email == _norm(body.email)))
    if user is not None:
        log_event(s, request, "password_reset_requested", user)
        try:
            _send_reset(s, user)
        except MailError:
            pass  # same answer either way; logged by send_mail
    return Message(message="If an account uses that email, a reset link is on its way.")


@router.post("/reset-password", response_model=Message)
def reset_password(body: ResetIn, request: Request, response: Response, s: SessionDep) -> Message:
    _limit(f"reset:{client_ip(request)}", 10, 900)
    user = consume_token(s, body.token, "reset_password")
    if user is None:
        raise HTTPException(400, "This reset link is invalid or has expired. Ask for a new one.")
    problem = password_problem(body.password, user.email)
    if problem:
        s.rollback()  # keep the link usable so they can try another password
        raise HTTPException(422, problem)
    user.password_hash = hash_password(body.password)
    user.email_verified = True  # they proved they read this inbox
    user.failed_logins, user.locked_until = 0, None
    end_all_sessions(s, user.id)
    log_event(s, request, "password_reset", user)
    clear_cookie(response)
    return Message(message="Password changed. Sign in with your new password.")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileIn, user: CurrentUser) -> UserOut:
    user.name = body.name.strip()
    return user_out(user)


@router.post("/change-password", response_model=Message)
def change_password(
    body: ChangePasswordIn, user: CurrentUser, request: Request, s: SessionDep, token: TokenCookie = None
) -> Message:
    _limit(f"change-pw:{user.id}", 5, 900)
    if user.password_hash is not None and not verify_password(
        user.password_hash, body.current_password or ""
    ):
        raise HTTPException(403, "Your current password is incorrect.")
    problem = password_problem(body.new_password, user.email)
    if problem:
        raise HTTPException(422, problem)
    user.password_hash = hash_password(body.new_password)
    end_all_sessions(s, user.id, keep_token=token)  # other devices are signed out
    log_event(s, request, "password_changed", user)
    return Message(message="Password updated. Other devices have been signed out.")


@router.delete("/me", response_model=Message)
def delete_me(
    body: DeleteIn, user: CurrentUser, request: Request, response: Response, s: SessionDep
) -> Message:
    _limit(f"delete:{user.id}", 5, 900)
    if body.confirm.strip().upper() != "DELETE":
        raise HTTPException(422, "Type DELETE to confirm.")
    if user.password_hash is not None and not verify_password(user.password_hash, body.password or ""):
        raise HTTPException(403, "Your password is incorrect.")
    case_ids = [str(c) for c in s.scalars(select(Case.id).where(Case.user_id == user.id))]
    log_event(s, request, "account_deleted", user)
    s.delete(user)  # cascades: sessions, tokens, cases, documents, facts, hearings
    s.flush()
    # Uploaded files are removed after the rows are gone; a failure is reported, not hidden.
    failed = []
    for cid in case_ids:
        folder = documents_mod.UPLOAD_ROOT / cid
        try:
            if folder.exists():
                shutil.rmtree(folder)
        except OSError:
            failed.append(cid)
    clear_cookie(response)
    if failed:
        raise HTTPException(
            500,
            "Your account was deleted, but some uploaded files could not be removed. "
            "Contact support so we can remove them.",
        )
    return Message(message="Your account and all your cases have been deleted.")


# ── Google ──


@router.get("/google/start")
def google_start(next: Annotated[str | None, Query(max_length=300)] = None) -> RedirectResponse:
    if not settings.google_enabled:
        raise HTTPException(404, "Google sign-in is not set up on this server.")
    state, verifier, challenge = google.new_flow()
    resp = RedirectResponse(google.authorize_url(state, challenge), status_code=302)
    resp.set_cookie(
        google.STATE_COOKIE,
        f"{state}|{verifier}|{_safe_next(next)}",
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",  # sent on Google's top-level redirect back to us
        path="/api/v1/auth/google",
    )
    return resp


@router.get("/google/callback")
def google_callback(
    request: Request,
    s: SessionDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    flow: Annotated[str | None, Cookie(alias=google.STATE_COOKIE)] = None,
) -> RedirectResponse:
    def fail(msg: str) -> RedirectResponse:
        r = RedirectResponse(f"/login?error={quote(msg)}", status_code=302)
        r.delete_cookie(google.STATE_COOKIE, path="/api/v1/auth/google")
        return r

    if not settings.google_enabled:
        return fail("Google sign-in is not set up on this server.")
    if error:
        return fail("Google sign-in was cancelled.")
    parts = (flow or "").split("|", 2)
    if not code or not state or len(parts) != 3 or parts[0] != state:
        return fail("The sign-in session expired. Please try again.")
    _limit(f"google:{client_ip(request)}", 20, 300)
    try:
        ident = google.exchange_code(code, parts[1])
    except google.GoogleError as e:
        return fail(str(e))
    if not ident.email_verified:
        return fail("Your Google account's email is not verified.")

    user = s.scalar(select(User).where(User.google_sub == ident.sub))
    if user is None:
        user = s.scalar(select(User).where(User.email == ident.email))
        if user is not None:
            # Google has verified this inbox, so it is the same person: link the accounts.
            user.google_sub = ident.sub
            if not user.email_verified:
                # The password was set by someone who never proved they own this inbox (it may be
                # an attacker who registered it first). Drop it, and any sessions it opened.
                user.password_hash = None
                s.flush()
                end_all_sessions(s, user.id)
            user.email_verified = True
            log_event(s, request, "google_linked", user)
        else:
            user = User(email=ident.email, name=ident.name, google_sub=ident.sub, email_verified=True)
            s.add(user)
            s.flush()
            log_event(s, request, "signup_google", user)
    resp = RedirectResponse(parts[2] if parts[2] != "/" else "/dashboard", status_code=302)
    resp.delete_cookie(google.STATE_COOKIE, path="/api/v1/auth/google")
    start_session(s, request, resp, user)
    log_event(s, request, "login_google", user)
    return resp
