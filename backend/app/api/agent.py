"""Agentic analysis of a case: start a run (background), follow its steps, list past runs.

The agent sends passages of the case's documents to the model, so it runs only for demo cases
until a no-retention model is configured (the same rule as hearings and document answers).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.jobs import agent_job
from app.api.hearing import get_hearing_llm, get_search_embedder, get_submit
from app.auth.deps import CurrentUser, case_for
from app.auth.limits import user_limit
from app.config import settings
from app.db.models import AgentRun
from app.db.session import get_session
from app.hearing.agents import LLM
from app.hearing.jobs import Submit
from app.retrieval.embedder import Embedder

router = APIRouter(prefix="/api/v1/cases", tags=["agent"])
SessionDep = Annotated[Session, Depends(get_session)]


class AgentIn(BaseModel):
    objective: str = Field(min_length=10, max_length=600)


class AgentRunOut(BaseModel):
    id: int
    objective: str
    model: str
    status: str
    error: str | None
    steps: list[dict[str, Any]]
    result: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None


def _out(r: AgentRun) -> AgentRunOut:
    return AgentRunOut(
        id=r.id,
        objective=r.objective,
        model=r.model,
        status=r.status,
        error=r.error,
        steps=r.steps or [],
        result=r.result or {},
        started_at=r.started_at,
        finished_at=r.finished_at,
    )


@router.post(
    "/{case_id}/agent",
    status_code=202,
    response_model=AgentRunOut,
    dependencies=[user_limit("agent", 6, 600)],
)
def start_agent(
    case_id: uuid.UUID,
    body: AgentIn,
    s: SessionDep,
    user: CurrentUser,
    llm: Annotated[LLM, Depends(get_hearing_llm)],
    embedder: Annotated[Embedder | None, Depends(get_search_embedder)],
    submit: Annotated[Submit, Depends(get_submit)],
) -> AgentRunOut:
    case = case_for(s, case_id, user, write=True)
    if not (case.is_demo or settings.private_llm_ok):
        raise HTTPException(
            403,
            "The agent sends passages of your documents to the model, which may retain data. It runs only "
            "for demo cases until a no-retention model is configured.",
        )
    run = AgentRun(
        case_id=case_id, objective=body.objective.strip(), model=llm.name, status="running", steps=[]
    )
    s.add(run)
    try:
        s.commit()
    except IntegrityError as e:
        s.rollback()
        raise HTTPException(409, "An analysis is already running for this case.") from e
    s.refresh(run)
    out = _out(run)
    submit(agent_job(run.id, llm, embedder))
    return out


@router.get("/{case_id}/agent/runs/{run_id}", response_model=AgentRunOut)
def get_agent_run(case_id: uuid.UUID, run_id: int, s: SessionDep, user: CurrentUser) -> AgentRunOut:
    case_for(s, case_id, user)
    r = s.get(AgentRun, run_id)
    if r is None or r.case_id != case_id:
        raise HTTPException(404, "Agent run not found.")
    return _out(r)


@router.get("/{case_id}/agent/runs", response_model=list[AgentRunOut])
def list_agent_runs(case_id: uuid.UUID, s: SessionDep, user: CurrentUser) -> list[AgentRunOut]:
    case_for(s, case_id, user)
    rows = s.scalars(
        select(AgentRun).where(AgentRun.case_id == case_id).order_by(AgentRun.started_at.desc()).limit(20)
    )
    return [_out(r) for r in rows]
