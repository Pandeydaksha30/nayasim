"""Search and question answering over a case's own uploaded documents.

- GET  /cases/{id}/passages   retrieval only, computed locally: allowed for every case.
- POST /cases/{id}/ask        sends the retrieved passages to the model: demo cases only, until a
                              model that does not retain data is configured (same rule as hearings).
- GET  /cases/{id}/questions  what was asked before.
- POST /cases/{id}/clauses    rights, obligations and penalties of each party (demo cases only),
                              every clause checked against the document; GET returns the latest.
Every route first checks that the signed-in user may read the case (404 otherwise), and every
search is restricted to that case.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.hearing import get_hearing_llm, get_search_embedder
from app.auth.deps import CurrentUser, case_for
from app.auth.limits import user_limit
from app.buyer.chunks import ensure_indexed
from app.config import settings
from app.db.models import CaseDocument, CaseQuestion
from app.db.session import get_session
from app.hearing.agents import LLM
from app.rag.answer import answer_question
from app.rag.clauses import analyse_clauses
from app.retrieval.case_search import search_case
from app.retrieval.embedder import Embedder

log = logging.getLogger("nyayasim.rag")
router = APIRouter(prefix="/api/v1/cases", tags=["document questions"])
SessionDep = Annotated[Session, Depends(get_session)]
EmbedderDep = Annotated[Embedder | None, Depends(get_search_embedder)]


def _index_missing(s: Session, case_id: uuid.UUID, embedder: Embedder | None) -> None:
    for doc_id in s.scalars(select(CaseDocument.id).where(CaseDocument.case_id == case_id)):
        ensure_indexed(s, doc_id, embedder)


@router.get("/{case_id}/passages", dependencies=[user_limit("passages", 60, 60)])
def passages(
    case_id: uuid.UUID,
    s: SessionDep,
    user: CurrentUser,
    embedder: EmbedderDep,
    q: Annotated[str, Query(min_length=3, max_length=400)],
    k: Annotated[int, Query(ge=1, le=12)] = 6,
) -> dict[str, Any]:
    """Passages of this case's documents that match the words. No model is called."""
    case_for(s, case_id, user)
    _index_missing(s, case_id, embedder)
    hits, mode = search_case(s, case_id, q, embedder, k=k)
    return {
        "query": q,
        "mode": mode,
        "source": "your uploaded documents",
        "hits": [
            {
                "chunk_id": h.chunk_id,
                "document_id": str(h.document_id),
                "filename": h.filename,
                "kind": h.kind,
                "page_no": h.page_no,
                "text": h.text,
                "score": h.score,
            }
            for h in hits
        ],
    }


class AskIn(BaseModel):
    question: str = Field(min_length=5, max_length=500)


@router.post("/{case_id}/ask", dependencies=[user_limit("ask", 20, 600)])
def ask(
    case_id: uuid.UUID,
    body: AskIn,
    s: SessionDep,
    user: CurrentUser,
    embedder: EmbedderDep,
    llm: Annotated[LLM, Depends(get_hearing_llm)],
) -> dict[str, Any]:
    """An answer grounded in this case's documents, with citations checked by code."""
    case = case_for(s, case_id, user)
    if not (case.is_demo or settings.private_llm_ok):
        raise HTTPException(
            403,
            "Answering sends passages of your documents to the model, which may retain data. It runs only "
            "for demo cases until a no-retention model is configured. Searching your documents works for "
            "every case.",
        )
    _index_missing(s, case_id, embedder)
    try:
        result = answer_question(s, case_id, body.question, llm, embedder)
    except Exception as e:  # noqa: BLE001 - the model service failed; say so, do not invent an answer
        log.exception("Document question failed for case %s", case_id)
        raise HTTPException(
            503, f"The model could not answer right now ({type(e).__name__}). Please try again in a minute."
        ) from e
    stored = {
        **result,
        # The history keeps which passages were used, not a second copy of the document text.
        "retrieved": [{k: v for k, v in r.items() if k != "text"} for r in result["retrieved"]],
    }
    if case.user_id != user.id:
        # A shared example case: answered, but nothing is written to a history every user can see.
        return {"id": None, **result}
    row = CaseQuestion(case_id=case_id, question=body.question, result=stored)
    s.add(row)
    s.commit()  # before the response, so the history shows it at once
    return {"id": row.id, **result}


@router.get("/{case_id}/questions")
def questions(case_id: uuid.UUID, s: SessionDep, user: CurrentUser) -> list[dict[str, Any]]:
    case_for(s, case_id, user)
    rows = s.scalars(
        select(CaseQuestion)
        .where(CaseQuestion.case_id == case_id, CaseQuestion.question != CLAUSES_KEY)
        .order_by(CaseQuestion.created_at.desc())
        .limit(50)
    )
    return [
        {"id": r.id, "question": r.question, "created_at": r.created_at.isoformat(), **r.result} for r in rows
    ]


# Clause analyses are kept in case_questions under this fixed "question" (no new table needed).
CLAUSES_KEY = "[contract clause analysis]"


@router.post("/{case_id}/clauses", dependencies=[user_limit("clauses", 6, 600)])
def clauses(
    case_id: uuid.UUID,
    s: SessionDep,
    user: CurrentUser,
    embedder: EmbedderDep,
    llm: Annotated[LLM, Depends(get_hearing_llm)],
) -> dict[str, Any]:
    """Rights, obligations and penalties of each party, each quoted and checked against the document."""
    case = case_for(s, case_id, user)
    if not (case.is_demo or settings.private_llm_ok):
        raise HTTPException(
            403,
            "Clause analysis sends passages of your documents to the model, which may retain data. It runs "
            "only for demo cases until a no-retention model is configured.",
        )
    _index_missing(s, case_id, embedder)
    try:
        result = analyse_clauses(s, case_id, llm, embedder)
    except Exception as e:  # noqa: BLE001 - the model service failed; say so, do not invent clauses
        log.exception("Clause analysis failed for case %s", case_id)
        raise HTTPException(
            503,
            f"The model could not analyse the contract right now ({type(e).__name__}). Please retry.",
        ) from e
    if case.user_id != user.id:
        return {"id": None, **result}
    row = CaseQuestion(case_id=case_id, question=CLAUSES_KEY, result=result)
    s.add(row)
    s.commit()
    return {"id": row.id, "created_at": row.created_at.isoformat() if row.created_at else None, **result}


@router.get("/{case_id}/clauses")
def latest_clauses(case_id: uuid.UUID, s: SessionDep, user: CurrentUser) -> dict[str, Any] | None:
    case_for(s, case_id, user)
    row = s.scalar(
        select(CaseQuestion)
        .where(CaseQuestion.case_id == case_id, CaseQuestion.question == CLAUSES_KEY)
        .order_by(CaseQuestion.created_at.desc())
        .limit(1)
    )
    return {"id": row.id, "created_at": row.created_at.isoformat(), **row.result} if row else None
