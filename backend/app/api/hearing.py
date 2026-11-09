"""Hearing API: run a simulated hearing for a case, read the latest run."""

from __future__ import annotations

import uuid
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, case_for
from app.buyer.facts import PrivateDataBlocked
from app.config import settings
from app.db.models import HearingRun
from app.db.session import get_session
from app.hearing.agents import LLM
from app.hearing.runner import HearingNotPossible, run_case_hearing
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


@router.post("/{case_id}/hearing", response_model=RunOut)
def run_hearing(
    case_id: uuid.UUID,
    s: SessionDep,
    user: CurrentUser,
    llm: Annotated[LLM, Depends(get_hearing_llm)],
    embedder: Annotated[Embedder | None, Depends(get_search_embedder)],
) -> RunOut:
    case_for(s, case_id, user, write=True)
    try:
        run = run_case_hearing(s, case_id, llm, embedder)
    except PrivateDataBlocked as e:
        raise HTTPException(403, str(e)) from e
    except HearingNotPossible as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:  # the failed run is stored by the runner; report the cause
        s.commit()
        raise HTTPException(502, f"The hearing could not be completed: {type(e).__name__}: {e}"[:500]) from e
    s.refresh(run)
    return _out(run)


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
