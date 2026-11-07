"""Facts from a buyer's documents, verified against the stored page text.

The model proposes each fact with a verbatim quote and its page. A fact is kept only if:
  * the quote is found on that page of the stored text (app.extraction.quotes.locate);
  * dates and amounts can be read from the *stored* matched text by deterministic code;
  * names and labels (builder, project, unit...) appear in the stored matched text.
The stored fact's quote is the stored text itself, so the database trigger (migration 0003)
can check it character for character.

Privacy: buyers' documents are private. They are sent to a model only if the case is a
fictional demo, or settings.private_llm_ok is set for a model that does not retain data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol

from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Case, CaseDocument, Fact
from app.extraction.order_fields import Evidence
from app.extraction.page_select import select_pages
from app.extraction.parsing import amounts_in, dates_in
from app.extraction.quotes import locate

PROMPT_VERSION = "buyer-facts-v1"
LOW_OCR_CONFIDENCE = 80.0

# key -> (label shown to the buyer, kind)
FACT_SPECS: dict[str, tuple[str, str]] = {
    "builder_name": ("Promoter (builder)", "text"),
    "project_name": ("Project", "text"),
    "rera_registration": ("Project registration", "text"),
    "unit": ("Unit", "text"),
    "agreement_date": ("Agreement date", "date"),
    "total_price": ("Total price", "amount"),
    "possession_promised": ("Promised possession", "date"),
    "delay_compensation_clause": ("Delay clause", "text"),
    "offer_of_possession_date": ("Offer of possession", "date"),
    "revised_completion_date": ("Builder's revised date", "date"),
    "escalation_demand": ("Extra charge demanded", "amount"),
}

BUYER_TERMS = [
    re.compile(p, re.I)
    for p in (
        r"possession",
        r"(?:total|sale)\s+(?:price|consideration)",
        r"received with thanks|receipt",
        r"\bpaid\b|payment",
        r"\bclause\b",
        r"compensation",
        r"registration",
        r"apartment|unit|flat",
        r"escalation|revised",
        r"rs\.?\s*\d|₹\s*\d",
    )
]


class PaymentEvidence(BaseModel):
    date: str | None = Field(None, description="Payment date as YYYY-MM-DD.")
    amount: str | None = Field(None, description="Amount in rupees, digits only.")
    quote: str | None = Field(
        None, description="Exact words copied from the document showing date and amount."
    )
    page_no: int | None = None


class ProposedBuyerFacts(BaseModel):
    builder_name: Evidence
    project_name: Evidence
    rera_registration: Evidence
    unit: Evidence
    agreement_date: Evidence
    total_price: Evidence
    possession_promised: Evidence
    delay_compensation_clause: Evidence
    offer_of_possession_date: Evidence
    revised_completion_date: Evidence
    escalation_demand: Evidence
    payments: list[PaymentEvidence] = Field(default_factory=list)


PROMPT = """You are reading a homebuyer's document ({kind}) about a flat bought from a builder in India.
Extract the facts below. For EVERY fact give:
  value   - the value, or null if this document does not clearly state it
  quote   - words copied EXACTLY from the document (no paraphrase, no "...", no corrections),
            short, and containing the value
  page_no - the page number from the "=== PAGE n ===" marker where the quote appears
Never guess, never compute, never combine numbers. Dates as YYYY-MM-DD; amounts in rupees, digits only.

Facts:
  builder_name, project_name, rera_registration (the project's RERA registration number), unit
  (flat number / size as written), agreement_date, total_price, possession_promised (date the
  builder promised to hand over possession), delay_compensation_clause (what the agreement says
  the builder pays for delay, as written), offer_of_possession_date, revised_completion_date
  (a new date the builder announced), escalation_demand (an extra charge demanded, in rupees),
  payments: every payment the buyer made, each with its own date, amount, quote and page_no.

DOCUMENT TEXT (selected pages; page numbers are the real ones):
{pages}
"""


class FactExtractor(Protocol):
    name: str

    def propose(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...


class PrivateDataBlocked(PermissionError):
    """Refused: real buyer documents may not go to a model that can retain data."""


@dataclass
class VerifiedFact:
    key: str
    label: str
    value: str
    page_no: int
    char_start: int
    char_end: int
    quote: str  # the stored page text at [char_start, char_end)
    confidence: str  # "high" | "review"


@dataclass
class FactResult:
    facts: list[VerifiedFact] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


def _decimal(raw: str | None) -> Decimal | None:
    try:
        return Decimal((raw or "").replace(",", "").strip()).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _iso_date(raw: str | None) -> date | None:
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def verify_facts(
    proposed: ProposedBuyerFacts, pages: dict[int, str], page_quality: dict[int, tuple[str, float | None]]
) -> FactResult:
    """``page_quality`` maps page_no -> (text_source, ocr_confidence) for the confidence label."""
    out = FactResult()

    def locate_ev(name: str, value, quote, page_no):
        base = {"field": name, "value": value, "quote": quote, "page_no": page_no}
        if not quote or page_no not in pages:
            out.rejected.append({**base, "reason": "missing quote or invalid page"})
            return None
        span = locate(quote, pages[page_no])
        if span is None:
            out.rejected.append({**base, "reason": f"quote not found on page {page_no}"})
            return None
        stored = pages[page_no][span.char_start : span.char_end]
        source, conf = page_quality.get(page_no, ("text_layer", None))
        weak = span.match != "exact" or (source == "ocr" and (conf or 0) < LOW_OCR_CONFIDENCE)
        return span, stored, "review" if weak else "high"

    def reject(name, value, quote, page_no, reason):
        out.rejected.append(
            {"field": name, "value": value, "quote": quote, "page_no": page_no, "reason": reason}
        )

    for key, (label, kind) in FACT_SPECS.items():
        ev: Evidence = getattr(proposed, key)
        if ev.value is None:
            continue
        got = locate_ev(key, ev.value, ev.quote, ev.page_no)
        if got is None:
            continue
        span, stored, confidence = got
        if kind == "date":
            d = _iso_date(ev.value)
            if d is None or d not in dates_in(stored):
                reject(key, ev.value, ev.quote, ev.page_no, "date not readable from the stored text")
                continue
            value = d.isoformat()
        elif kind == "amount":
            a = _decimal(ev.value)
            if a is None or a not in amounts_in(stored):
                reject(key, ev.value, ev.quote, ev.page_no, "amount not readable from the stored text")
                continue
            value = str(a)
        else:
            if fuzz.partial_ratio(ev.value.lower(), stored.lower()) < 85:
                reject(key, ev.value, ev.quote, ev.page_no, "value not found in the stored text")
                continue
            value = ev.value.strip()
        out.facts.append(
            VerifiedFact(key, label, value, ev.page_no, span.char_start, span.char_end, stored, confidence)
        )

    seen: set[tuple[str, str]] = set()
    for i, pay in enumerate(proposed.payments):
        name = f"payments[{i}]"
        got = locate_ev(name, f"{pay.date} {pay.amount}", pay.quote, pay.page_no)
        if got is None:
            continue
        span, stored, confidence = got
        d, a = _iso_date(pay.date), _decimal(pay.amount)
        if d is None or d not in dates_in(stored):
            reject(name, pay.date, pay.quote, pay.page_no, "payment date not readable from the stored text")
            continue
        if a is None or a not in amounts_in(stored):
            reject(
                name, pay.amount, pay.quote, pay.page_no, "payment amount not readable from the stored text"
            )
            continue
        if (d.isoformat(), str(a)) in seen:
            continue  # the same payment quoted twice
        seen.add((d.isoformat(), str(a)))
        out.facts.append(
            VerifiedFact(
                "payment",
                "Payment",
                f"{d.isoformat()};{a}",
                pay.page_no,
                span.char_start,
                span.char_end,
                stored,
                confidence,
            )
        )
    return out


def build_prompt(kind: str, pages: dict[int, str]) -> str:
    body = "\n\n".join(f"=== PAGE {n} ===\n{t}" for n, t in sorted(pages.items()))
    return PROMPT.format(kind=kind.replace("_", " "), pages=body)


def extract_case_facts(session: Session, case_id, extractor: FactExtractor) -> dict:
    """Extract and store facts for every document of a case. Unconfirmed facts from an earlier
    run are replaced; facts the buyer confirmed are kept."""
    case = session.get(Case, case_id)
    if case is None:
        raise LookupError("Case not found.")
    if not (case.is_demo or settings.private_llm_ok):
        raise PrivateDataBlocked(
            "Real buyer documents are not sent to the configured model because it may retain data. "
            "Configure a no-retention model (NYAYASIM_PRIVATE_LLM_OK=true) or use a demo case."
        )
    summary = {"documents": 0, "facts": 0, "rejected": [], "errors": []}
    docs = session.scalars(select(CaseDocument).where(CaseDocument.case_id == case_id)).all()
    for doc in docs:
        pages = {p.page_no: p.text for p in doc.pages}
        quality = {
            p.page_no: (p.text_source, float(p.ocr_confidence) if p.ocr_confidence else None)
            for p in doc.pages
        }
        try:
            proposed = extractor.propose(
                build_prompt(doc.kind, select_pages(pages, terms=BUYER_TERMS)), ProposedBuyerFacts
            )
        except Exception as e:  # reported per document; other documents still processed
            summary["errors"].append({"document": doc.filename, "error": f"{type(e).__name__}: {e}"[:300]})
            continue
        result = verify_facts(proposed, pages, quality)
        session.execute(delete(Fact).where(Fact.document_id == doc.id, Fact.confirmed.is_(False)))
        for f in result.facts:
            session.add(
                Fact(
                    case_id=case_id,
                    document_id=doc.id,
                    key=f.key,
                    label=f.label,
                    value=f.value,
                    page_no=f.page_no,
                    char_start=f.char_start,
                    char_end=f.char_end,
                    quote=f.quote,
                    confidence=f.confidence,
                )
            )
        summary["documents"] += 1
        summary["facts"] += len(result.facts)
        summary["rejected"] += [{"document": doc.filename, **r} for r in result.rejected]
    session.flush()
    return summary
