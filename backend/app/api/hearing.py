"""Hearing API: start a simulated hearing (runs in the background), follow it, read the latest."""

from __future__ import annotations

import uuid
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, case_for
from app.buyer.facts import PrivateDataBlocked
from app.config import settings
from app.db.models import HearingRun
from app.db.session import get_session
from app.hearing.agents import LLM
from app.hearing.jobs import Submit, default_submit, hearing_job
from app.hearing.runner import HearingNotPossible, prepare_case_hearing
from app.retrieval.embedder import Embedder

router = APIRouter(prefix="/api/v1/cases", tags=["hearing"])
SessionDep = Annotated[Session, Depends(get_session)]


def get_hearing_llm() -> LLM:
    if settings.gemini_api_key is None:
        raise HTTPException(503, "No model is configured for the hearing (GEMINI_API_KEY is not set).")
    from app.extraction.gemini import GeminiExtractor

    return GeminiExtractor(
        settings.gemini_api_key.get_secret_value(),
        settings.hearing_model,
        min_interval_s=0,
        thinking=settings.hearing_thinking,
    )


@lru_cache(maxsize=1)
def _embedder() -> Embedder:
    from app.retrieval.embedder import LocalEmbedder

    return LocalEmbedder(
        settings.embedding_model, settings.embedding_query_prefix, settings.embedding_doc_prefix
    )


def get_search_embedder() -> Embedder | None:
    return _embedder()


class RunOut(BaseModel):
    id: int
    status: str
    error: str | None
    cutoff: str
    models: str
    started_at: datetime
    finished_at: datetime | None
    result: dict[str, Any]


def _out(run: HearingRun) -> RunOut:
    return RunOut(
        id=run.id,
        status=run.status,
        error=run.error,
        cutoff=run.cutoff.isoformat(),
        models=run.models,
        started_at=run.started_at,
        finished_at=run.finished_at,
        result=run.result,
    )


def get_submit() -> Submit:
    return default_submit


@router.post("/{case_id}/hearing", status_code=202, response_model=RunOut)
def run_hearing(
    case_id: uuid.UUID,
    s: SessionDep,
    user: CurrentUser,
    llm: Annotated[LLM, Depends(get_hearing_llm)],
    embedder: Annotated[Embedder | None, Depends(get_search_embedder)],
    submit: Annotated[Submit, Depends(get_submit)],
) -> RunOut:
    """Checks run now (privacy, facts, precedents) so problems are reported at once; the model calls
    then run in the background. Poll GET /hearing/runs/{id} until status is not 'running'."""
    case_for(s, case_id, user, write=True)
    try:
        prep = prepare_case_hearing(s, case_id, embedder)
    except PrivateDataBlocked as e:
        raise HTTPException(403, str(e)) from e
    except HearingNotPossible as e:
        raise HTTPException(422, str(e)) from e
    run = HearingRun(case_id=case_id, cutoff=prep.cutoff, models=llm.name, status="running")
    s.add(run)
    try:
        s.commit()  # the job reads the row from its own session
    except IntegrityError as e:  # the unique index: one running hearing per case
        s.rollback()
        raise HTTPException(
            409, "A hearing for this case is already running. It will appear when done."
        ) from e
    s.refresh(run)
    out = _out(run)
    submit(hearing_job(run.id, prep, llm))
    return out


@router.get("/{case_id}/hearing/runs/{run_id}", response_model=RunOut)
def get_run(case_id: uuid.UUID, run_id: int, s: SessionDep, user: CurrentUser) -> RunOut:
    case_for(s, case_id, user)
    run = s.get(HearingRun, run_id)
    if run is None or run.case_id != case_id:
        raise HTTPException(404, "Hearing run not found.")
    return _out(run)


@router.get("/{case_id}/hearing/active", response_model=RunOut | None)
def active_run(case_id: uuid.UUID, s: SessionDep, user: CurrentUser) -> RunOut | None:
    """The hearing currently running for this case, if any (so a reloaded page keeps waiting)."""
    case_for(s, case_id, user)
    run = s.scalar(select(HearingRun).where(HearingRun.case_id == case_id, HearingRun.status == "running"))
    return _out(run) if run else None


@router.get("/{case_id}/hearing", response_model=RunOut)
def latest_hearing(case_id: uuid.UUID, s: SessionDep, user: CurrentUser) -> RunOut:
    case_for(s, case_id, user)
    run = s.scalar(
        select(HearingRun)
        .where(HearingRun.case_id == case_id, HearingRun.status == "completed")
        .order_by(HearingRun.started_at.desc())
        .limit(1)
    )
    if run is None:
        raise HTTPException(404, "No hearing has been run for this case yet.")
    return _out(run)
