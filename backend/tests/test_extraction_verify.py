"""Verification of proposed fields, and the runner end to end with a stand-in model."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import CaseRecord, Order, OrderPage
from app.extraction.order_fields import PROMPT_VERSION, Evidence, ProposedFields, verify
from app.extraction.runner import ExtractReport, extract_order, pending_for_extraction, reviewed_ids

PAGES = {
    1: "Complaint No. RERA-GRG-1-2024\nThe complainant booked a unit and paid a sum of "
    "Rs. 57,60,000/- to the respondent. As per clause 7.1 the due date of possession was 30.06.2021.",
    2: "The respondent submitted that the delay was due to force majeure including NGT bans.\n"
    "ORDER\nThe complaint is allowed. The respondent shall pay interest at the prescribed rate i.e. 10.85% "
    "per annum for every month of delay.",
}


def ev(value, quote, page):
    return Evidence(value=value, quote=quote, page_no=page)


def good_proposal(**overrides) -> ProposedFields:
    base = dict(
        claim_type=ev("delayed_possession", "pay interest at the prescribed rate", 2),
        outcome=ev("allowed", "The complaint is allowed.", 2),
        possession_due=ev("2021-06-30", "the due date of possession was 30.06.2021", 1),
        amount_paid=ev("5760000", "paid a sum of Rs. 57,60,000/-", 1),
        award_amount=Evidence(),
        interest_rate_pct=ev("10.85", "prescribed rate i.e. 10.85% per annum", 2),
        defences=[ev("force majeure", "the delay was due to force majeure including NGT bans", 2)],
    )
    base.update(overrides)
    return ProposedFields(**base)


def test_all_verifiable_fields_are_accepted_with_sources():
    v = verify(good_proposal(), PAGES)
    assert v.storable and v.rejected == []
    assert (v.claim_type, v.outcome) == ("delayed_possession", "allowed")
    assert v.possession_due == date(2021, 6, 30)
    assert v.amount_paid == Decimal("5760000.00")
    assert v.interest_rate_pct == Decimal("10.85")
    assert v.award_amount is None  # null in, null out
    src = v.sources["amount_paid"]
    assert "57,60,000" in PAGES[1][src["char_start"] : src["char_end"]]
    assert v.defences == ["force majeure"]


def test_quote_on_wrong_page_is_rejected():
    v = verify(good_proposal(outcome=ev("allowed", "The complaint is allowed.", 1)), PAGES)
    assert v.outcome is None and not v.storable
    assert "not found on page 1" in v.rejected[0]["reason"]


def test_amount_the_model_computed_is_rejected():
    # The quote is real, but 5800000 is not written in it.
    v = verify(good_proposal(amount_paid=ev("5800000", "paid a sum of Rs. 57,60,000/-", 1)), PAGES)
    assert v.amount_paid is None
    assert v.rejected[0]["reason"] == "amount not readable from the stored text"


def test_model_correcting_a_number_in_its_quote_cannot_change_the_stored_value():
    # The page says 57,60,000. The model quotes and claims 57,80,000: the quote aligns closely,
    # but the amount is read from the stored text, so the claim is rejected.
    proposal = good_proposal(
        amount_paid=ev("5780000", "booked a unit and paid a sum of Rs. 57,80,000/- to the respondent", 1)
    )
    v = verify(proposal, PAGES)
    assert v.amount_paid is None
    assert v.rejected[0]["reason"] == "amount not readable from the stored text"


def test_source_records_how_the_quote_matched():
    v = verify(good_proposal(), PAGES)
    assert v.sources["outcome"]["match"] == "exact"


def test_date_not_in_quote_is_rejected():
    v = verify(
        good_proposal(possession_due=ev("2021-12-30", "the due date of possession was 30.06.2021", 1)), PAGES
    )
    assert v.possession_due is None


def test_rate_with_percent_sign_value_is_accepted():
    v = verify(
        good_proposal(interest_rate_pct=ev("10.85%", "prescribed rate i.e. 10.85% per annum", 2)), PAGES
    )
    assert v.interest_rate_pct == Decimal("10.85")


def test_unknown_outcome_label_is_rejected():
    v = verify(good_proposal(outcome=ev("won", "The complaint is allowed.", 2)), PAGES)
    assert v.outcome is None and "not one of" in v.rejected[0]["reason"]


def test_paraphrased_quote_is_rejected():
    v = verify(good_proposal(outcome=ev("allowed", "The authority allowed the complaint.", 2)), PAGES)
    assert not v.storable


def test_page_number_that_does_not_exist_is_rejected():
    v = verify(good_proposal(outcome=ev("allowed", "The complaint is allowed.", 9)), PAGES)
    assert not v.storable and v.rejected[0]["reason"] == "missing quote or invalid page"


# ── Runner with the database ──


class StandIn:
    name = "stand-in"

    def __init__(self, proposal=None, error: Exception | None = None):
        self.proposal, self.error, self.calls = proposal, error, 0

    def propose(self, prompt: str) -> ProposedFields:
        self.calls += 1
        assert "=== PAGE 1 ===" in prompt and "=== PAGE 2 ===" in prompt
        if self.error:
            raise self.error
        return self.proposal


@pytest.fixture
def fetched_order(db_engine):
    from datetime import UTC, datetime

    wipe = text("TRUNCATE orders, fetch_log RESTART IDENTITY CASCADE")
    with db_engine.begin() as c:
        c.execute(wipe)
    with Session(db_engine) as s:
        o = Order(
            source="hrera_gurugram",
            complaint_no="RERA-GRG-1-2024",
            case_type="HRERA Complaints",
            decided_on=date(2024, 6, 1),
            pdf_url="u",
            pdf_sha256="a" * 64,
            page_count=2,
            text_source="text_layer",
            fetched_at=datetime.now(UTC),
        )
        for n, t in PAGES.items():
            o.pages.append(OrderPage(page_no=n, text=t, text_source="text_layer"))
        s.add(o)
        s.commit()
        oid = o.id
    yield db_engine, oid
    with db_engine.begin() as c:
        c.execute(wipe)


def test_runner_stores_record_whose_sources_point_at_real_text(fetched_order, tmp_path):
    engine, oid = fetched_order
    report = ExtractReport()
    assert pending_for_extraction(engine, 10) == [oid]
    status = extract_order(engine, oid, StandIn(good_proposal()), tmp_path / "review.jsonl", report)
    assert status.startswith("stored")
    with Session(engine) as s:
        rec = s.get(CaseRecord, oid)
        assert rec.outcome == "allowed" and rec.interest_rate_pct == Decimal("10.850")
        assert rec.extracted_by == f"stand-in:{PROMPT_VERSION}"
        src = rec.field_sources["possession_due"]
        page = s.scalar(select(OrderPage.text).where(OrderPage.order_id == oid, OrderPage.page_no == 1))
        assert "30.06.2021" in page[src["char_start"] : src["char_end"]]
    assert pending_for_extraction(engine, 10) == []


def test_unverifiable_outcome_goes_to_review_not_to_database(fetched_order, tmp_path):
    engine, oid = fetched_order
    log = tmp_path / "review.jsonl"
    bad = good_proposal(outcome=ev("allowed", "made up sentence not in the order", 2))
    status = extract_order(engine, oid, StandIn(bad), log, ExtractReport())
    assert "needs review" in status
    with Session(engine) as s:
        assert s.get(CaseRecord, oid) is None
    entry = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert entry["order_id"] == oid and entry["rejected"][0]["field"] == "outcome"
    assert pending_for_extraction(engine, 10, skip=reviewed_ids(log)) == []


def test_model_error_is_reported_and_order_stays_pending(fetched_order, tmp_path):
    engine, oid = fetched_order
    report = ExtractReport()
    status = extract_order(
        engine, oid, StandIn(error=RuntimeError("quota exceeded")), tmp_path / "r.jsonl", report
    )
    assert status == "error" and "quota exceeded" in report.errors[0][1]
    assert pending_for_extraction(engine, 10) == [oid]


def test_merge_review_logs_after_retry(tmp_path):
    from app.extraction.runner import merge_review_logs

    review, retry = tmp_path / "review.jsonl", tmp_path / "retry.jsonl"
    review.write_text("".join(json.dumps({"order_id": i, "rejected": []}) + "\n" for i in (1, 2, 3, 4)))
    retry.write_text(json.dumps({"order_id": 2, "rejected": [{"field": "outcome"}]}) + "\n")
    # 1 was stored on retry, 2 failed again (new entry), 3 errored (keeps old), 4 not retried.
    remaining = merge_review_logs(review, {1, 2}, retry)
    lines = [json.loads(x) for x in review.read_text().splitlines()]
    assert remaining == 3
    assert sorted(x["order_id"] for x in lines) == [2, 3, 4]
    assert next(x for x in lines if x["order_id"] == 2)["rejected"] == [{"field": "outcome"}]
    assert not retry.exists()
