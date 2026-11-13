"""Agent runs in the background (same pattern as app/hearing/jobs.py). Each step is saved as it
happens, so the page can show progress; the final result and status are saved at the end."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agent.orchestrator import run_orchestrator
from app.agent.tools import ToolContext
from app.db.models import AgentRun, Case
from app.db.session import get_engine
from app.hearing.agents import LLM
from app.retrieval.embedder import Embedder

log = logging.getLogger("nyayasim.agent")


def execute_agent_run(s: Session, run: AgentRun, llm: LLM, embedder: Embedder | None) -> AgentRun:
    case = s.get(Case, run.case_id)
    ctx = ToolContext(
        s=s, case_id=run.case_id, claim_type=case.claim_type, cutoff=date.today(), embedder=embedder, llm=llm
    )
    run_id = run.id

    def on_step(entry: dict) -> None:
        r = s.get(AgentRun, run_id)
        r.steps = [*(r.steps or []), entry]
        flag_modified(r, "steps")
        s.commit()

    try:
        result = run_orchestrator(ctx, run.objective, on_step)
    except Exception as e:
        s.rollback()
        r = s.get(AgentRun, run_id)
        r.status, r.error, r.finished_at = "failed", f"{type(e).__name__}: {e}"[:1000], datetime.now(UTC)
        s.commit()
        raise
    r = s.get(AgentRun, run_id)
    r.result = result
    complete = not result["error"] and result["stop_reason"] in ("agent chose to finish",)
    r.status = "completed" if complete else "incomplete"
    r.finished_at = datetime.now(UTC)
    s.commit()
    return r


def agent_job(run_id: int, llm: LLM, embedder: Embedder | None) -> Callable[[], None]:
    def job() -> None:
        with Session(get_engine()) as s:
            run = s.get(AgentRun, run_id)
            if run is None:
                return
            try:
                execute_agent_run(s, run, llm, embedder)
            except Exception:
                log.exception("Agent run %s failed", run_id)

    return job


def fail_interrupted_agent_runs() -> int:
    with Session(get_engine()) as s:
        n = s.execute(
            update(AgentRun)
            .where(AgentRun.status == "running")
            .values(
                status="failed",
                error="Interrupted: the server restarted during the run. Please start it again.",
                finished_at=datetime.now(UTC),
            )
        ).rowcount
        s.commit()
    return n or 0
