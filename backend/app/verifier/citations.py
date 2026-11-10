"""Citation checker: the gate between the hearing agents and the judge.

Every citation an agent makes is checked by code against the order store. Any failed rule
rejects it; the argument that relies on it is then removed (step 8), so an invented or
misquoted precedent never reaches the buyer.

Rules:
  1. the order exists in the store (by id and/or complaint number);
  2. id and complaint number, when both given, are the same order;
  3. the order's text is stored (it was fetched);
  4. it was decided strictly before the case's cutoff date;
  5. if a set of allowed orders is given (the search results for this case), it is in it;
  6. the quote is on the cited page (min 20 characters; exact, or >= 90% similar for OCR
     noise in letters, but every number identical to the stored text), and the verdict
     returns the *stored* text and its offsets;
  7. a claimed outcome must match the verified case record when one exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CaseRecord, Order, OrderPage
from app.extraction.quotes import locate

MIN_QUOTE_CHARS = 20


def _numbers(s: str) -> list[str]:
    """Digit runs in order, ignoring thousands separators ("72,00,000" -> "7200000")."""
    return re.findall(r"\d+", re.sub(r"(?<=\d),(?=\d)", "", s))


# Words that decide what a legal sentence means. A quote may differ from the stored text by a few
# OCR letters, but never in these: "is liable" vs "is not liable" is 4 characters apart yet says
# the opposite (benchmark of 10 Nov 2026: 45 of 47 such flips passed the similarity check alone).
MEANING_WORDS = frozenset(
    {
        "not", "no", "nor", "never", "neither", "without", "cannot", "unless", "except",
        "allowed", "dismissed", "rejected", "granted", "denied", "disallowed", "withdrawn",
        "entitled", "liable", "shall", "may", "must", "valid", "invalid", "void",
    }
)  # fmt: skip


def _meaning_words(s: str) -> list[str]:
    words = re.findall(r"[a-z]+", s.lower().replace("n't", " not"))
    return [w for w in words if w in MEANING_WORDS]


@dataclass(frozen=True)
class Citation:
    page_no: int
    quote: str
    order_id: int | None = None
    complaint_no: str | None = None
    claimed_outcome: str | None = None


@dataclass
class Verdict:
    citation: Citation
    reasons: list[str] = field(default_factory=list)  # why it was rejected; empty = verified
    notes: list[str] = field(default_factory=list)  # checks that could not be made
    order_id: int | None = None
    complaint_no: str | None = None
    decided_on: date | None = None
    char_start: int | None = None
    char_end: int | None = None
    stored_quote: str | None = None
    match: str | None = None

    @property
    def verified(self) -> bool:
        return not self.reasons

    @property
    def status(self) -> str:
        return "verified" if self.verified else "rejected"


def _find_order(s: Session, c: Citation, v: Verdict, source: str) -> Order | None:
    order = s.get(Order, c.order_id) if c.order_id is not None else None
    if c.order_id is not None and order is None:
        v.reasons.append(f"order id {c.order_id} is not in the store")
        return None
    if c.complaint_no:
        matches = s.scalars(
            select(Order).where(Order.source == source, Order.complaint_no == c.complaint_no.strip())
        ).all()
        if order is not None:
            if order.complaint_no != c.complaint_no.strip():
                v.reasons.append(f"order id {order.id} is {order.complaint_no}, not {c.complaint_no.strip()}")
                return None
        elif not matches:
            v.reasons.append(f"complaint {c.complaint_no.strip()} is not in the store")
            return None
        elif len(matches) > 1:
            v.reasons.append(
                f"complaint {c.complaint_no.strip()} has {len(matches)} decisions; cite the order id"
            )
            return None
        else:
            order = matches[0]
    if order is None:
        v.reasons.append("citation names no order")
    return order


def verify_citation(
    s: Session,
    c: Citation,
    *,
    before: date,
    allowed_orders: set[int] | None = None,
    source: str = "hrera_gurugram",
) -> Verdict:
    if not isinstance(before, date):
        raise TypeError("verify_citation() needs the case's cutoff date")
    v = Verdict(citation=c)
    order = _find_order(s, c, v, source)
    if order is None:
        return v
    v.order_id, v.complaint_no, v.decided_on = order.id, order.complaint_no, order.decided_on

    if order.fetched_at is None:
        v.reasons.append("the order's text is not stored, so the quote cannot be checked")
    if order.decided_on >= before:
        v.reasons.append(f"decided on {order.decided_on}, not before the cutoff {before}")
    if allowed_orders is not None and order.id not in allowed_orders:
        v.reasons.append("not among the orders retrieved for this case")

    quote = (c.quote or "").strip()
    page = s.get(OrderPage, (order.id, c.page_no))
    if page is None:
        if order.fetched_at is not None:
            v.reasons.append(f"page {c.page_no} does not exist in this order")
    elif len(" ".join(quote.split())) < MIN_QUOTE_CHARS:
        v.reasons.append(f"quote too short to verify (at least {MIN_QUOTE_CHARS} characters)")
    else:
        span = locate(quote, page.text)
        if span is None:
            v.reasons.append(f"quote not found on page {c.page_no}")
        else:
            v.char_start, v.char_end, v.match = span.char_start, span.char_end, span.match
            v.stored_quote = page.text[span.char_start : span.char_end]
            # A near match tolerates OCR noise in letters, never in numbers: a changed date,
            # amount, rate or section number is a misquote.
            quoted, stored = _numbers(quote), _numbers(v.stored_quote)
            if quoted != stored:
                v.reasons.append(
                    f"numbers in the quote ({', '.join(quoted) or 'none'}) differ from the stored text "
                    f"({', '.join(stored) or 'none'})"
                )
            # The aligner may cut the stored span mid-word ("is allowe"); compare whole words.
            lo, hi = span.char_start, span.char_end
            while lo > 0 and page.text[lo - 1].isalpha():
                lo -= 1
            while hi < len(page.text) and page.text[hi].isalpha():
                hi += 1
            q_words, s_words = _meaning_words(quote), _meaning_words(page.text[lo:hi])
            if q_words != s_words:
                v.reasons.append(
                    f"wording that decides the meaning ({' '.join(q_words) or 'none'}) differs from "
                    f"the stored text ({' '.join(s_words) or 'none'})"
                )

    if c.claimed_outcome:
        record = s.get(CaseRecord, order.id)
        if record is None:
            v.notes.append("claimed outcome not checked: no verified record for this order yet")
        elif record.outcome != c.claimed_outcome:
            v.reasons.append(
                f"says the outcome was {c.claimed_outcome}, but the record says {record.outcome}"
            )
    return v


def verify_all(
    s: Session, citations: list[Citation], *, before: date, allowed_orders: set[int] | None = None
) -> list[Verdict]:
    return [verify_citation(s, c, before=before, allowed_orders=allowed_orders) for c in citations]
