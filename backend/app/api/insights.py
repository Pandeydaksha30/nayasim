"""Search over public orders, outcome estimate, complaint draft and the classifier demo.

All four are computed locally from stored data: no external model is called, so they work for
every case (not only demo cases) and send nothing outside this server.
"""

from __future__ import annotations

import uuid
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.hearing import get_search_embedder
from app.auth.deps import CurrentUser, case_for
from app.db.models import CaseRecord, Fact
from app.db.session import get_session
from app.insights.draft import build_draft
from app.insights.estimate import outcome_estimate
from app.ml.claim_rule import relief_claim
from app.retrieval.embedder import Embedder
from app.retrieval.search import search

router = APIRouter(prefix="/api/v1", tags=["insights"])
SessionDep = Annotated[Session, Depends(get_session)]
MODELS = Path(__file__).resolve().parents[3] / "data" / "models"

# Measured once on the held-out test orders (MODEL_TRAINING_GUIDE.md). Shown with every prediction.
MEASURED = {
    "claim_type": {"accuracy_pct": 74.3, "macro_f1": 0.455, "test_orders": 74, "majority_baseline_pct": 73.0},
    "outcome": {"accuracy_pct": 50.8, "macro_f1": 0.340, "test_orders": 59, "majority_baseline_pct": 57.6},
}
CAVEAT = (
    "Trained on machine-extracted labels that have not been checked by people. Not a basis for a decision."
)


class HitOut(BaseModel):
    order_id: int
    complaint_no: str
    decided_on: date
    page_no: int
    text: str
    outcome: str | None
    claim_type: str | None


class SearchOut(BaseModel):
    query: str
    mode: str
    before: date
    notes: list[str]
    hits: list[HitOut]


@router.get("/search/orders", response_model=SearchOut)
async def search_orders(
    s: SessionDep,
    user: CurrentUser,
    embedder: Annotated[Embedder | None, Depends(get_search_embedder)],
    q: Annotated[str, Query(min_length=3, max_length=400)],
    k: Annotated[int, Query(ge=1, le=20)] = 10,
) -> SearchOut:
    """Hybrid (keyword + vector) search over the stored public HRERA Gurugram orders."""
    today = date.today()
    res = await run_in_threadpool(search, s, q, before=today, embedder=embedder, k=k)
    records = {
        r.order_id: r
        for r in s.scalars(select(CaseRecord).where(CaseRecord.order_id.in_({h.order_id for h in res.hits})))
    }
    hits = [
        HitOut(
            order_id=h.order_id,
            complaint_no=h.complaint_no,
            decided_on=h.decided_on,
            page_no=h.page_no,
            text=h.text,
            outcome=records[h.order_id].outcome if h.order_id in records else None,
            claim_type=records[h.order_id].claim_type if h.order_id in records else None,
        )
        for h in res.hits
    ]
    return SearchOut(query=q, mode=res.mode, before=today, notes=res.notes, hits=hits)


@router.get("/cases/{case_id}/estimate")
def case_estimate(case_id: uuid.UUID, s: SessionDep, user: CurrentUser) -> dict[str, Any]:
    """Rule-based outcome estimate from how past orders with the same claim type and delay ended."""
    case = case_for(s, case_id, user)
    promised = s.scalar(
        select(Fact.value).where(Fact.case_id == case_id, Fact.key == "possession_promised").order_by(Fact.id)
    )
    due = None
    if promised:
        try:
            due = date.fromisoformat(promised)
        except ValueError:
            due = None
    return outcome_estimate(s, case.claim_type, due, date.today())


@router.get("/cases/{case_id}/draft")
def case_draft(case_id: uuid.UUID, s: SessionDep, user: CurrentUser) -> dict[str, Any]:
    """Complaint draft assembled by code from verified facts and checked citations."""
    return build_draft(s, case_for(s, case_id, user))


class OrderTextIn(BaseModel):
    text: str = Field(min_length=200, max_length=60_000)


@lru_cache(maxsize=2)
def _model(task: str):
    path = MODELS / f"{task}_tfidf_lr.joblib"
    if not path.exists():
        raise HTTPException(
            503, f"The {task} model has not been trained on this server (run scripts.train_classifier)."
        )
    import joblib

    return joblib.load(path)


def _predict(task: str, text: str) -> dict[str, Any]:
    model = _model(task)
    probs = model.predict_proba([text])[0]
    ranked = sorted(zip(model.classes_, probs, strict=True), key=lambda x: -x[1])
    return {"label": ranked[0][0], "scores": {c: round(float(p), 3) for c, p in ranked}}


@router.post("/predictions/order-text")
def classify_order_text(body: OrderTextIn, user: CurrentUser) -> dict[str, Any]:
    """The trained classifiers applied to the parties' part of an order (facts, relief sought, reply).

    Claim type: the relief-section rule decides where it finds clear wording, otherwise the TF-IDF
    model. Outcome: the TF-IDF model. Both are reported with their measured test accuracy.
    """
    rule = relief_claim(body.text)
    claim_model = _predict("claim_type", body.text)
    return {
        "claim_type": {
            "label": rule or claim_model["label"],
            "decided_by": "relief-section rule" if rule else "TF-IDF + logistic regression",
            "model_scores": claim_model["scores"],
            "measured": MEASURED["claim_type"],
        },
        "outcome": {
            **_predict("outcome", body.text),
            "decided_by": "TF-IDF + logistic regression",
            "measured": MEASURED["outcome"],
            "note": "This model scored below the simple baseline on held-out orders.",
        },
        "caveat": CAVEAT,
    }
