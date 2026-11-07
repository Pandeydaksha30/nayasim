"""Inputs to a hearing: the case summary (from verified facts) and the precedent set (from search).

Both are built by code. The agents see the case only through `summary_text` and precedents
only through `precedent_block`; they can cite nothing else.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CaseAnswer, CaseRecord, Fact
from app.retrieval.embedder import Embedder
from app.retrieval.search import search


@dataclass
class CaseInput:
    claim_type: str
    cutoff: date
    facts: dict[str, list[str]] = field(default_factory=dict)
    answers: dict[str, str] = field(default_factory=dict)

    def first(self, key: str) -> str | None:
        return (self.facts.get(key) or [None])[0]

    @property
    def payments(self) -> list[tuple[date, Decimal]]:
        out = []
        for v in self.facts.get("payment", []):
            d, a = v.split(";")
            out.append((date.fromisoformat(d), Decimal(a)))
        return sorted(out)


def from_buyer_case(s: Session, case_id: uuid.UUID, claim_type: str, cutoff: date) -> CaseInput:
    ci = CaseInput(claim_type=claim_type, cutoff=cutoff)
    for f in s.scalars(select(Fact).where(Fact.case_id == case_id).order_by(Fact.id)):
        values = ci.facts.setdefault(f.key, [])
        if f.value not in values:
            values.append(f.value)
    ci.answers = {
        a.question_id: a.answer for a in s.scalars(select(CaseAnswer).where(CaseAnswer.case_id == case_id))
    }
    return ci


LABELS = {
    "builder_name": "Builder",
    "project_name": "Project",
    "unit": "Unit",
    "agreement_date": "Agreement date",
    "total_price": "Total price (Rs)",
    "possession_promised": "Possession promised by",
    "delay_compensation_clause": "Agreement's delay clause",
    "offer_of_possession_date": "Offer of possession",
    "revised_completion_date": "Builder's revised completion date",
    "escalation_demand": "Extra charge demanded (Rs)",
}
ANSWER_LABELS = {
    "offer_of_possession": "Offer of possession received?",
    "payments_complete": "All payments listed?",
    "missed_instalments": "Missed or late instalments?",
    "relief": "Relief the buyer wants",
    "escalation_paid": "Extra charge paid?",
}


def summary_text(ci: CaseInput) -> str:
    lines = [f"Claim: {ci.claim_type.replace('_', ' ')}. Hearing as of {ci.cutoff.isoformat()}."]
    for key, label in LABELS.items():
        if (v := ci.first(key)) is not None:
            lines.append(f"- {label}: {v}")
    pays = ci.payments
    if pays:
        total = sum((a for _, a in pays), Decimal(0))
        lines.append(f"- Payments by the buyer: {len(pays)}, total Rs {total}")
        lines += [f"    {d.isoformat()}: Rs {a}" for d, a in pays]
    else:
        lines.append("- Payments by the buyer: none verified")
    for qid, label in ANSWER_LABELS.items():
        if qid in ci.answers:
            lines.append(f"- {label} {ci.answers[qid]}")
    return "\n".join(lines)


def search_query(ci: CaseInput) -> str:
    parts = ["delay in handing over possession", "interest for every month of delay", "force majeure"]
    if ci.claim_type == "refund" or "refund" in ci.answers.get("relief", "").lower():
        parts.append("refund of the amount paid with interest withdraw from the project")
    if ci.first("escalation_demand"):
        parts.append("escalation charges demanded by the promoter")
    if ci.first("revised_completion_date"):
        parts.append("revised completion date extension of registration")
    if ci.answers.get("missed_instalments", "").startswith("Yes"):
        parts.append("allottee defaulted in payment of instalments")
    return "; ".join(parts)


@dataclass
class Precedent:
    ref: str  # "P1", "P2", ... — the only way agents may name an order
    order_id: int
    complaint_no: str
    decided_on: date
    outcome: str | None
    interest_rate_pct: Decimal | None
    excerpts: list[tuple[int, str]]  # (page_no, text)


def build_precedents(s: Session, ci: CaseInput, embedder: Embedder | None, k: int = 12) -> list[Precedent]:
    result = search(s, search_query(ci), before=ci.cutoff, embedder=embedder, k=k)
    by_order: dict[int, Precedent] = {}
    for h in result.hits:
        p = by_order.get(h.order_id)
        if p is None:
            rec = s.get(CaseRecord, h.order_id)
            p = Precedent(
                f"P{len(by_order) + 1}",
                h.order_id,
                h.complaint_no,
                h.decided_on,
                rec.outcome if rec else None,
                rec.interest_rate_pct if rec else None,
                [],
            )
            by_order[h.order_id] = p
        p.excerpts.append((h.page_no, h.text))
    return list(by_order.values())


def precedent_block(precedents: list[Precedent]) -> str:
    out = []
    for p in precedents:
        outcome = p.outcome.replace("_", " ") if p.outcome else "not recorded"
        out.append(f"[{p.ref}] {p.complaint_no}, decided {p.decided_on.isoformat()}, outcome: {outcome}")
        for page, text in p.excerpts:
            out.append(f"  page {page}: {' '.join(text.split())}")
    return "\n".join(out)
