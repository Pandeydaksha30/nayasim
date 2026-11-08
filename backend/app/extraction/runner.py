"""Run field extraction over fetched orders and store verified case records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.models import CaseRecord, Order, OrderPage
from app.extraction.order_fields import PROMPT_VERSION, Extractor, build_prompt, verify
from app.extraction.page_select import select_pages


@dataclass
class ExtractReport:
    attempted: int = 0
    stored: int = 0
    needs_review: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    fields_accepted: int = 0
    fields_rejected: int = 0
    pages_sent: int = 0
    pages_total: int = 0


def pending_for_extraction(
    engine: Engine, limit: int, case_type: str = "HRERA Complaints", skip: set[int] | None = None
) -> list[int]:
    q = (
        select(Order.id)
        .outerjoin(CaseRecord, CaseRecord.order_id == Order.id)
        .where(Order.fetched_at.is_not(None), Order.case_type == case_type, CaseRecord.order_id.is_(None))
        .order_by(Order.decided_on, Order.id)
    )
    with Session(engine) as s:
        ids = [i for i in s.scalars(q) if not skip or i not in skip]
    return ids[:limit]


def reviewed_ids(review_log: Path) -> set[int]:
    """Orders already sent to the review file (not retried automatically)."""
    if not review_log.exists():
        return set()
    return {
        json.loads(line)["order_id"] for line in review_log.read_text(encoding="utf-8").splitlines() if line
    }


def merge_review_logs(review_log: Path, retried: set[int], retry_log: Path) -> int:
    """After a retry pass: keep entries that were not retried, plus the retried orders that
    failed again (from ``retry_log``). Returns how many orders remain for review."""

    def read(p: Path) -> list[str]:
        return [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln] if p.exists() else []

    kept = [ln for ln in read(review_log) if json.loads(ln)["order_id"] not in retried]
    again = read(retry_log)
    review_log.write_text("".join(ln + "\n" for ln in kept + again), encoding="utf-8")
    retry_log.unlink(missing_ok=True)
    return len(kept) + len(again)


def extract_order(
    engine: Engine, order_id: int, extractor: Extractor, review_log: Path, report: ExtractReport
) -> str:
    with Session(engine) as s:
        order = s.get(Order, order_id)
        pages = {
            p.page_no: p.text for p in s.scalars(select(OrderPage).where(OrderPage.order_id == order_id))
        }
        label = f"{order.complaint_no} ({order.decided_on})"
        complaint_no = order.complaint_no
        s.commit()  # end the read transaction: none may stay open during the model call
        report.attempted += 1
        try:
            # Only key pages go to the model; verification below uses all stored pages.
            sent = select_pages(pages)
            report.pages_sent += len(sent)
            report.pages_total += len(pages)
            proposed = extractor.propose(build_prompt(sent))
        except Exception as e:  # API/network/parse errors: reported, order stays pending
            report.errors.append((label, f"{type(e).__name__}: {e}"[:300]))
            return "error"

        result = verify(proposed, pages)
        report.fields_accepted += len(result.sources)
        report.fields_rejected += len(result.rejected)

        if not result.storable:
            review_log.parent.mkdir(parents=True, exist_ok=True)
            with review_log.open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "order_id": order_id,
                            "complaint_no": complaint_no,
                            "at": datetime.now(UTC).isoformat(),
                            "rejected": result.rejected,
                        },
                        default=str,
                    )
                    + "\n"
                )
            report.needs_review += 1
            return "needs review (outcome or claim type not verifiable)"

        s.add(
            CaseRecord(
                order_id=order_id,
                claim_type=result.claim_type,
                outcome=result.outcome,
                possession_due=result.possession_due,
                amount_paid=result.amount_paid,
                award_amount=result.award_amount,
                interest_rate_pct=result.interest_rate_pct,
                defences=result.defences,
                field_sources={**result.sources, "_rejected": result.rejected},
                extracted_by=f"{extractor.name}:{PROMPT_VERSION}",
            )
        )
        s.commit()
        report.stored += 1
        return f"stored ({len(result.sources)} fields, {len(result.rejected)} rejected)"
