"""Outcome estimate for a buyer's case from the claim x delay rule (app/backtest/baselines.py).

The rule is the best-measured outcome method so far (72.9% on 59 held-out orders, against
machine-extracted labels; MODEL_EVALUATION.md). It counts how past orders with the same claim type
and a similar delay ended. Everything is computed locally from stored records; nothing about the
case is sent anywhere.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from sqlalchemy.orm import Session

from app.backtest.baselines import MIN_BUCKET, Buckets, delay_band
from app.backtest.dataset import Example, load

MEASURED = {
    "accuracy_pct": 72.9,
    "test_cases": 59,
    "note": "Measured on held-out orders decided from 2025; labels are machine-extracted and unchecked.",
}
BAND_LABEL = {"<2y": "under 2 years", "2-4y": "2 to 4 years", ">4y": "over 4 years", "unknown": "unknown"}


def outcome_estimate(s: Session, claim_type: str, possession_due: date | None, as_of: date) -> dict:
    train = load(s, as_of, split="train")
    if not train:
        return {"available": False, "reason": "no past orders with a recorded outcome"}
    rule = Buckets(train)
    case = Example(0, "", as_of, claim_type, possession_due, None, "")
    band = delay_band(case)
    bucket = rule.by_bucket.get((claim_type, band), [])
    by_claim = rule.by_claim.get(claim_type, [])
    if len(bucket) >= MIN_BUCKET:
        used, basis = bucket, f"past orders with the same claim type and a delay of {BAND_LABEL[band]}"
    elif len(by_claim) >= MIN_BUCKET:
        used, basis = by_claim, "past orders with the same claim type (too few with a similar delay)"
    else:
        used, basis = [e.outcome for e in train], "all past orders (too few with the same claim type)"
    return {
        "available": True,
        "predicted": rule.predict(case),
        "basis": basis,
        "counts": dict(Counter(used)),
        "orders_used": len(used),
        "delay_months": case.delay_months,
        "delay_band": BAND_LABEL[band],
        "as_of": as_of.isoformat(),
        "method": "claim type x delay rule",
        "measured": MEASURED,
    }
