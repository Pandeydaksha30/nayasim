"""Citation verifier benchmark.

Ground truth comes from the order store itself, so no labels are invented:
- GENUINE citations quote a real span of a real stored page of a test-split order, cited with the
  right order and page, at a cutoff after the decision. Two kinds: exact, and with OCR-like noise
  (two letters changed, numbers untouched), which the verifier is designed to accept.
- FABRICATED citations are made from genuine ones by one known change each: a number altered,
  the wrong page, an order that does not exist, a quote taken from a different order, an order
  decided after the cutoff, the words shuffled, or a quote too short to check.

The verifier is rule-based and is not trained on any of this, so evaluating it on generated
cases does not leak; the cases still come only from the frozen test split.

Metrics: precision of "verified" (share of accepted citations that are genuine), recall of
genuine citations, and the catch rate per fabrication type.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderPage
from app.extraction.quotes import locate
from app.verifier.citations import Citation, verify_citation

KINDS_GENUINE = ("exact", "ocr_noise")
KINDS_FAKE = (
    "number_changed",
    "wrong_page",
    "nonexistent_order",
    "quote_from_other_order",
    "decided_after_cutoff",
    "words_shuffled",
    "too_short",
    "meaning_flipped",
)


@dataclass
class Case:
    kind: str
    genuine: bool
    citation: Citation
    cutoff: object  # date


def _span(text: str, rng: random.Random, lo: int = 80, hi: int = 160) -> str | None:
    words = list(re.finditer(r"\S+", text))
    if len(words) < 25:
        return None
    for _ in range(10):
        i = rng.randrange(0, len(words) - 20)
        j = i
        while j < len(words) - 1 and words[j].end() - words[i].start() < rng.randint(lo, hi):
            j += 1
        span = text[words[i].start() : words[j].end()]
        if lo <= len(span) <= hi + 40 and sum(ch.isalpha() for ch in span) > len(span) * 0.6:
            return span
    return None


def _noise(span: str, rng: random.Random) -> str:
    """Two letters swapped for another letter: OCR-like, numbers untouched."""
    chars = list(span)
    letters = [i for i, ch in enumerate(chars) if ch.isalpha()]
    for i in rng.sample(letters, min(2, len(letters))):
        chars[i] = "e" if chars[i].lower() != "e" else "a"
    return "".join(chars)


def _change_number(span: str, rng: random.Random) -> str | None:
    nums = list(re.finditer(r"\d+", span))
    if not nums:
        return None
    m = rng.choice(nums)
    old = m.group()
    new = str(int(old) + rng.randint(1, 9)).zfill(len(old))
    return span[: m.start()] + new + span[m.end() :]


_FLIPS = [
    (r"\bis entitled\b", "is not entitled"),
    (r"\bshall\b", "shall not"),
    (r"\bis liable\b", "is not liable"),
    (r"\ballowed\b", "dismissed"),
    (r"\bdismissed\b", "allowed"),
    (r"\bhas been\b", "has not been"),
    (r"\bwas\b", "was not"),
    (r"\bis\b", "is not"),
]


def _flip_meaning(span: str) -> str | None:
    """One small wording change that reverses the legal meaning (a few characters only, so a
    similarity threshold alone does not catch it)."""
    for pattern, repl in _FLIPS:
        if re.search(pattern, span):
            return re.sub(pattern, repl, span, count=1)
    return None


def build_cases(
    s: Session, test_order_ids: list[int], n_pages: int = 150, seed: int = 20261110
) -> list[Case]:
    rng = random.Random(seed)
    pages = s.execute(
        select(OrderPage.order_id, OrderPage.page_no, OrderPage.text)
        .where(OrderPage.order_id.in_(test_order_ids), func.length(OrderPage.text) > 600)
        .order_by(OrderPage.order_id, OrderPage.page_no)
    ).all()
    rng.shuffle(pages)
    decided = dict(s.execute(select(Order.id, Order.decided_on).where(Order.id.in_(test_order_ids))).all())
    max_id = s.scalar(select(func.max(Order.id))) or 0
    page_counts = dict(
        s.execute(
            select(OrderPage.order_id, func.max(OrderPage.page_no))
            .where(OrderPage.order_id.in_(test_order_ids))
            .group_by(OrderPage.order_id)
        ).all()
    )

    cases: list[Case] = []
    used = 0
    for order_id, page_no, text in pages:
        if used >= n_pages:
            break
        span = _span(text, rng)
        if span is None:
            continue
        used += 1
        after = decided[order_id] + timedelta(days=1)

        def add(kind, genuine, quote, page=page_no, oid=order_id, cutoff=after):
            cases.append(Case(kind, genuine, Citation(page_no=page, quote=quote, order_id=oid), cutoff))

        add("exact", True, span)
        add("ocr_noise", True, _noise(span, rng))
        if (changed := _change_number(span, rng)) is not None:
            add("number_changed", False, changed)
        other_page = page_no + 1 if page_no < page_counts[order_id] else page_no - 1
        if other_page >= 1 and other_page != page_no:
            other_text = s.get(OrderPage, (order_id, other_page))
            # Orders repeat boilerplate (e.g. the text of Section 18) on several pages: only a page
            # where the quote really is absent makes a "wrong page" case.
            if other_text is not None and locate(span, other_text.text) is None:
                add("wrong_page", False, span, page=other_page)
        add("nonexistent_order", False, span, oid=max_id + 1000 + used)
        # A real quote from a different order, cited to this one.
        donor = pages[rng.randrange(len(pages))]
        if donor[0] != order_id and (donor_span := _span(donor[2], rng)) and locate(donor_span, text) is None:
            add("quote_from_other_order", False, donor_span)
        add("decided_after_cutoff", False, span, cutoff=decided[order_id])
        words = span.split()
        shuffled = words[:]
        while shuffled == words and len(words) > 3:
            rng.shuffle(shuffled)
        add("words_shuffled", False, " ".join(shuffled))
        add("too_short", False, " ".join(words[:2])[:15])
        flipped = _flip_meaning(span)
        # A "flip" that recreates the page's real wording (span ended at "is" before "not") is true.
        if flipped is not None and " ".join(flipped.split()) not in " ".join(text.split()):
            add("meaning_flipped", False, flipped)
    return cases


def evaluate(s: Session, cases: list[Case]) -> dict:
    per_kind: dict[str, dict] = {}
    tp = fp = fn = tn = 0
    misses: list[dict] = []
    for c in cases:
        v = verify_citation(s, c.citation, before=c.cutoff)
        accepted = not v.reasons
        k = per_kind.setdefault(c.kind, {"genuine": c.genuine, "n": 0, "accepted": 0})
        k["n"] += 1
        k["accepted"] += accepted
        if c.genuine and accepted:
            tp += 1
        elif c.genuine:
            fn += 1
            if len(misses) < 20:
                misses.append(
                    {
                        "kind": c.kind,
                        "order_id": c.citation.order_id,
                        "page": c.citation.page_no,
                        "reasons": v.reasons,
                    }
                )
        elif accepted:
            fp += 1
            if len(misses) < 20:
                misses.append(
                    {
                        "kind": c.kind,
                        "order_id": c.citation.order_id,
                        "page": c.citation.page_no,
                        "quote": c.citation.quote[:120],
                        "accepted_wrongly": True,
                    }
                )
        else:
            tn += 1
    for k in per_kind.values():
        k["rate"] = round(k["accepted"] / k["n"], 4) if k["n"] else None  # acceptance rate
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return {
        "cases": len(cases),
        "genuine": tp + fn,
        "fabricated": fp + tn,
        "confusion": {
            "genuine_accepted": tp,
            "genuine_rejected": fn,
            "fake_accepted": fp,
            "fake_rejected": tn,
        },
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "fabrication_catch_rate": round(tn / (tn + fp), 4) if tn + fp else None,
        "per_kind": per_kind,
        "examples_of_errors": misses,
    }
