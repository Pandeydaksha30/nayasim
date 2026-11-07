"""Structured outcome extraction for regulator orders, with code-side verification.

The model only *proposes* each field together with a verbatim quote and its page. This
module accepts a field only if:

1. the quote is found on that page of the stored text (whitespace/case-insensitive), and
2. for dates, amounts and rates, the value can be read from the quote by deterministic
   code (app.extraction.parsing) — the model's own arithmetic is never trusted;
3. for categories, the value is one of the allowed labels.

Rejected fields are kept (with the reason) for human review, never stored as facts.
An order whose outcome or claim type cannot be verified gets no case record at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol

from pydantic import BaseModel, Field

from app.extraction.parsing import amounts_in, dates_in, rates_in
from app.extraction.quotes import locate

PROMPT_VERSION = "order-fields-v1"

CLAIM_TYPES = ("delayed_possession", "refund", "other")
OUTCOMES = ("allowed", "partly_allowed", "dismissed", "withdrawn", "other")


class Evidence(BaseModel):
    value: str | None = Field(None, description="The value, or null if the order does not state it.")
    quote: str | None = Field(None, description="Exact words copied from the order that state the value.")
    page_no: int | None = Field(
        None, description="Page number (from the === PAGE n === markers) of the quote."
    )


class ProposedFields(BaseModel):
    claim_type: Evidence
    outcome: Evidence
    possession_due: Evidence
    amount_paid: Evidence
    award_amount: Evidence
    interest_rate_pct: Evidence
    defences: list[Evidence] = Field(default_factory=list)


PROMPT = """You are reading an order of a Real Estate Regulatory Authority in India.
Extract the fields below. For EVERY field give:
  value   - the value, or null if the order does not clearly state it
  quote   - words copied EXACTLY from the order (no paraphrase, no "...", no corrections),
            short (one sentence or clause) and containing the value
  page_no - the page number from the "=== PAGE n ===" marker where the quote appears
Never guess. Never compute. If a value is not written in the order, return null for all three.

Fields:
  claim_type: "delayed_possession" (buyer keeps the unit, seeks delay interest),
              "refund" (buyer withdraws, seeks refund), or "other"
  outcome: what the authority decided on the complainant's main relief: "allowed",
           "partly_allowed", "dismissed", "withdrawn", or "other"
  possession_due: the due date of possession the authority used, as YYYY-MM-DD
  amount_paid: total amount paid by the complainant, in rupees, digits only (e.g. 5760000)
  award_amount: a total amount the respondent is ordered to pay, in rupees, digits only;
                null if the order only directs interest without stating a total
  interest_rate_pct: the interest rate applied, as a number (e.g. 10.85)
  defences: up to 5 objections the respondent (builder) raised; value = a short label,
            quote = the respondent's argument as written

ORDER TEXT:
{pages}
"""


class Extractor(Protocol):
    name: str

    def propose(self, prompt: str) -> ProposedFields: ...


@dataclass
class Verified:
    claim_type: str | None = None
    outcome: str | None = None
    possession_due: date | None = None
    amount_paid: Decimal | None = None
    award_amount: Decimal | None = None
    interest_rate_pct: Decimal | None = None
    defences: list[str] = field(default_factory=list)
    sources: dict[str, dict] = field(default_factory=dict)
    rejected: list[dict] = field(default_factory=list)

    @property
    def storable(self) -> bool:
        return self.claim_type is not None and self.outcome is not None


def build_prompt(pages: dict[int, str]) -> str:
    body = "\n\n".join(f"=== PAGE {n} ===\n{text}" for n, text in sorted(pages.items()))
    return PROMPT.format(pages=body)


def _decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        return None


def _check(name: str, ev: Evidence, pages: dict[int, str], out: Verified) -> tuple[str, dict, str] | None:
    """Return (value, source, stored_text) if the evidence holds up, else record a rejection.

    ``stored_text`` is the matched span of the stored page. Values must be read from it, not
    from the model's quote, so a model that "corrects" a number cannot change what is stored.
    """
    if ev.value is None:
        return None
    reject = {"field": name, "value": ev.value, "quote": ev.quote, "page_no": ev.page_no}
    if not ev.quote or ev.page_no not in pages:
        out.rejected.append({**reject, "reason": "missing quote or invalid page"})
        return None
    span = locate(ev.quote, pages[ev.page_no])
    if span is None:
        out.rejected.append({**reject, "reason": f"quote not found on page {ev.page_no}"})
        return None
    source = {
        "page_no": ev.page_no,
        "char_start": span.char_start,
        "char_end": span.char_end,
        "match": span.match,
    }
    return ev.value.strip(), source, pages[ev.page_no][span.char_start : span.char_end]


def verify(proposed: ProposedFields, pages: dict[int, str]) -> Verified:
    out = Verified()

    def reject(name: str, ev: Evidence, reason: str) -> None:
        out.rejected.append(
            {"field": name, "value": ev.value, "quote": ev.quote, "page_no": ev.page_no, "reason": reason}
        )

    for name, allowed in (("claim_type", CLAIM_TYPES), ("outcome", OUTCOMES)):
        ev = getattr(proposed, name)
        if (got := _check(name, ev, pages, out)) is None:
            continue
        value, source, _stored = got
        if value not in allowed:
            reject(name, ev, f"value not one of {allowed}")
            continue
        setattr(out, name, value)
        out.sources[name] = source

    ev = proposed.possession_due
    if (got := _check("possession_due", ev, pages, out)) is not None:
        value, source, stored = got
        try:
            wanted = date.fromisoformat(value)
        except ValueError:
            reject("possession_due", ev, "value is not YYYY-MM-DD")
        else:
            if wanted in dates_in(stored):
                out.possession_due, out.sources["possession_due"] = wanted, source
            else:
                reject("possession_due", ev, "date not readable from the stored text")

    for name in ("amount_paid", "award_amount"):
        ev = getattr(proposed, name)
        if (got := _check(name, ev, pages, out)) is None:
            continue
        value, source, stored = got
        wanted = _decimal(value)
        if wanted is None or wanted.quantize(Decimal("0.01")) not in amounts_in(stored):
            reject(name, ev, "amount not readable from the stored text")
            continue
        setattr(out, name, wanted.quantize(Decimal("0.01")))
        out.sources[name] = source

    ev = proposed.interest_rate_pct
    if (got := _check("interest_rate_pct", ev, pages, out)) is not None:
        value, source, stored = got
        wanted = _decimal(value.rstrip("%"))
        if wanted is None or wanted not in rates_in(stored):
            reject("interest_rate_pct", ev, "rate not readable from the stored text")
        else:
            out.interest_rate_pct, out.sources["interest_rate_pct"] = wanted, source

    for i, ev in enumerate(proposed.defences[:5]):
        if (got := _check(f"defences[{i}]", ev, pages, out)) is not None:
            value, source, _stored = got
            out.sources[f"defences[{len(out.defences)}]"] = source
            out.defences.append(value)

    return out
