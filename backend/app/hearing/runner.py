"""Run a hearing for a buyer case and store the run (completed or failed)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.buyer.facts import PrivateDataBlocked
from app.config import settings
from app.db.models import Case, HearingRun
from app.hearing.agents import LLM
from app.hearing.graph import run_graph
from app.hearing.inputs import build_precedents, from_buyer_case
from app.retrieval.embedder import Embedder


class HearingNotPossible(ValueError):
    """A hearing cannot be based on real precedent; the message is shown to the user."""


def run_case_hearing(
    s: Session, case_id: uuid.UUID, llm: LLM, embedder: Embedder | None, cutoff: date | None = None
) -> HearingRun:
    case = s.get(Case, case_id)
    if case is None:
        raise LookupError("Case not found.")
    if not (case.is_demo or settings.private_llm_ok):
        raise PrivateDataBlocked(
            "A hearing sends the case facts to the model, which may retain data. It runs only for demo "
            "cases until a no-retention model is configured (NYAYASIM_PRIVATE_LLM_OK=true)."
        )
    cutoff = cutoff or date.today()
    ci = from_buyer_case(s, case_id, case.claim_type, cutoff)
    if not ci.facts:
        raise HearingNotPossible("No verified facts yet. Upload documents and find facts first.")
    precedents = build_precedents(s, ci, embedder)
    if not (s.new or s.dirty or s.deleted):
        s.commit()  # no transaction stays open during the model calls
    if not precedents:
        raise HearingNotPossible(
            f"No similar orders decided before {cutoff} were found to base a hearing on."
        )

    run = HearingRun(case_id=case_id, cutoff=cutoff, models=llm.name, status="completed")
    try:
        run.result = run_graph(s, llm, ci, precedents, as_of=cutoff)
    except Exception as e:  # stored as a failed run and re-raised: never a silent half-result
        run.status, run.error = "failed", f"{type(e).__name__}: {e}"[:1000]
        run.finished_at = datetime.now(UTC)
        s.add(run)
        s.flush()
        raise
    run.finished_at = datetime.now(UTC)
    s.add(run)
    s.flush()
    return run
