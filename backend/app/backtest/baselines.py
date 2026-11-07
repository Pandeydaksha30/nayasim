"""The two code-only baselines (no model).

1. Majority: always predict the most common outcome among training records.
2. Buckets: most common outcome among training records with the same claim type and delay
   band (under 2 years, 2-4 years, over 4 years, unknown). Falls back to the claim type, then
   to the overall majority, when a bucket has fewer than MIN_BUCKET records. This stands in for
   the plan's "simple model on structured facts": with ~100 training records a fitted
   classifier would not be more reliable, and this one is easy to explain.
"""

from __future__ import annotations

from collections import Counter

from app.backtest.dataset import Example

MIN_BUCKET = 3


def _most_common(items: list[str]) -> str:
    c = Counter(items)
    top = max(c.values())
    return sorted(k for k, v in c.items() if v == top)[0]  # deterministic tie-break


def delay_band(e: Example) -> str:
    m = e.delay_months
    if m is None:
        return "unknown"
    return "<2y" if m < 24 else "2-4y" if m <= 48 else ">4y"


class Majority:
    name = "majority"

    def __init__(self, train: list[Example]) -> None:
        if not train:
            raise ValueError("no training records")
        self.label = _most_common([e.outcome for e in train])

    def predict(self, e: Example) -> str:
        return self.label


class Buckets:
    name = "claim type x delay"

    def __init__(self, train: list[Example]) -> None:
        if not train:
            raise ValueError("no training records")
        self.overall = _most_common([e.outcome for e in train])
        self.by_claim: dict[str, list[str]] = {}
        self.by_bucket: dict[tuple[str, str], list[str]] = {}
        for e in train:
            self.by_claim.setdefault(e.claim_type, []).append(e.outcome)
            self.by_bucket.setdefault((e.claim_type, delay_band(e)), []).append(e.outcome)

    def predict(self, e: Example) -> str:
        bucket = self.by_bucket.get((e.claim_type, delay_band(e)), [])
        if len(bucket) >= MIN_BUCKET:
            return _most_common(bucket)
        claim = self.by_claim.get(e.claim_type, [])
        if len(claim) >= MIN_BUCKET:
            return _most_common(claim)
        return self.overall
