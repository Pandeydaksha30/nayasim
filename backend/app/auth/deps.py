"""FastAPI dependencies: the signed-in user, and case access checks."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.service import SESSION_COOKIE, user_for_token
from app.db.models import Case, User
from app.db.session import get_session


def optional_user(
    s: Annotated[Session, Depends(get_session)],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User | None:
    return user_for_token(s, token)


def current_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(401, "Please sign in.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def can_read(case: Case, user: User) -> bool:
    """Own cases, plus shared fictional demo cases that belong to nobody."""
    return case.user_id == user.id or (case.user_id is None and case.is_demo)


def case_for(s: Session, case_id: uuid.UUID, user: User, write: bool = False) -> Case:
    """The case if this user may use it. Someone else's case is reported as not found, so case ids
    cannot be probed. Shared demo cases are read-only (write=True needs the owner)."""
    case = s.get(Case, case_id)
    if case is None or not can_read(case, user):
        raise HTTPException(404, "Case not found.")
    if write and case.user_id != user.id:
        raise HTTPException(
            403, "This shared example case is read-only. Create your own case to make changes."
        )
    return case
