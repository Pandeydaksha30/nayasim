"""Numbers for the report, all computed by code.

* Outcome shares: counted from the verified case records of the retrieved precedents, with a
  90% Wilson interval for "buyer wins" (allowed or partly allowed). Fewer than MIN_RECORDS
  records -> "insufficient precedent", no percentage.
* Award: the deterministic calculator, using the buyer's verified payments and promised date,
  at the median interest rate applied in the precedents that record one. No rate in any
  precedent -> no award figure.
"""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal
from statistics import median

from app.calculator.interest import Payment, delay_interest, refund_with_interest
from app.hearing.inputs import CaseInput, Precedent

MIN_RECORDS = 5
Z90 = 1.6449


def wilson(successes: int, n: int, z: float = Z90) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def outcome_shares(precedents: list[Precedent]) -> dict:
    recorded = [p.outcome for p in precedents if p.outcome]
    counts: dict[str, int] = {}
    for o in recorded:
        counts[o] = counts.get(o, 0) + 1
    n = len(recorded)
    out = {"precedents": len(precedents), "with_record": n, "counts": counts}
    if n < MIN_RECORDS:
        out["insufficient"] = True
        out["note"] = (
            f"Only {n} of {len(precedents)} similar orders have a verified outcome; "
            f"at least {MIN_RECORDS} needed."
        )
        return out
    wins = counts.get("allowed", 0) + counts.get("partly_allowed", 0)
    lo, hi = wilson(wins, n)
    out.update(insufficient=False, buyer_wins=round(wins / n, 3), interval_90=[round(lo, 3), round(hi, 3)])
    return out


def award(ci: CaseInput, precedents: list[Precedent], as_of: date) -> dict:
    rates = [p.interest_rate_pct for p in precedents if p.interest_rate_pct is not None]
    payments = [Payment(d, a, "") for d, a in ci.payments]
    promised = ci.first("possession_promised")
    if not payments:
        return {"available": False, "reason": "no verified payments"}
    if not rates:
        return {"available": False, "reason": "no similar order records an interest rate"}
    rate = Decimal(str(median(rates))).quantize(Decimal("0.001"))
    out = {
        "available": True,
        "rate_pct": str(rate),
        "rate_basis": f"median of {len(rates)} rate(s) applied in similar orders decided before {ci.cutoff}",
        "principal": str(sum((p.amount for p in payments), Decimal(0))),
        "as_of": as_of.isoformat(),
    }
    refund = refund_with_interest(payments, as_of, rate)
    out["refund_total"] = str(refund.total)
    if promised:
        out["delay_interest"] = str(
            delay_interest(payments, date.fromisoformat(promised), as_of, rate).interest
        )
        out["possession_due"] = promised
    else:
        out["delay_interest"] = None
        out["delay_note"] = "promised possession date not verified"
    return out
