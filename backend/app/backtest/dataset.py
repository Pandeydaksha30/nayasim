"""Time-split backtest data: train on records decided before the cutoff, test on later ones.

A test case is built only from structured facts known before its decision (claim type, amount
paid, promised possession date, hearing date). Nothing from the order's text — which states
the decision — is used, and precedents are restricted to orders decided before the cutoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CaseRecord, Order
from app.hearing.inputs import CaseInput

CLASSES = ("allowed", "partly_allowed", "dismissed")  # decided on the merits


@dataclass(frozen=True)
class Example:
    order_id: int
    complaint_no: str
    decided_on: date
    claim_type: str
    possession_due: date | None
    amount_paid: Decimal | None
    outcome: str  # the truth; never part of the input

    @property
    def delay_months(self) -> int | None:
        if self.possession_due is None:
            return None
        d = (self.decided_on - self.possession_due).days
        return max(0, round(d / 30.44))


def load(
    s: Session, cutoff: date, *, split: str, source: str = "hrera_gurugram", until: date | None = None
) -> list[Example]:
    """split='train' -> decided before cutoff; 'test' -> on/after cutoff (and before `until`, if
    given: a validation year). Merits outcomes only."""
    q = (
        select(Order, CaseRecord)
        .join(CaseRecord, CaseRecord.order_id == Order.id)
        .where(Order.source == source, CaseRecord.outcome.in_(CLASSES))
        .where(Order.decided_on < cutoff if split == "train" else Order.decided_on >= cutoff)
        .order_by(Order.decided_on, Order.id)
    )
    if until is not None and split == "test":
        q = q.where(Order.decided_on < until)
    return [
        Example(o.id, o.complaint_no, o.decided_on, r.claim_type, r.possession_due, r.amount_paid, r.outcome)
        for o, r in s.execute(q)
    ]


def case_input(e: Example, cutoff: date) -> CaseInput:
    """The facts a buyer would know before the hearing; precedents limited to the cutoff."""
    facts: dict[str, list[str]] = {}
    if e.possession_due:
        facts["possession_promised"] = [e.possession_due.isoformat()]
    if e.amount_paid is not None:
        facts["amount_paid_total"] = [str(e.amount_paid)]
    facts["hearing_date"] = [e.decided_on.isoformat()]
    return CaseInput(claim_type=e.claim_type, cutoff=cutoff, facts=facts)
