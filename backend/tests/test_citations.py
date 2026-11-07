"""Step 7: the citation checker — one test per rule, plus the verified path."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import CaseRecord, Order, OrderPage
from app.verifier.citations import Citation, verify_all, verify_citation

P1 = "Complaint No. 101 of 2022\nThe respondent pleaded force majeure due to the NGT ban on construction."
P2 = (
    "ORDER\nThe plea of force majeure is rejected. The complaint is allowed and the respondent\n"
    "shall pay interest at the prescribed rate for every month of delay."
)
CUTOFF = date(2025, 1, 1)


def order(no, decided, pages=None, fetched=True):
    o = Order(
        source="hrera_gurugram",
        complaint_no=no,
        case_type="HRERA Complaints",
        decided_on=decided,
        pdf_url="u",
        pdf_sha256="d" * 64 if fetched else None,
        page_count=len(pages or []) or None,
        text_source="text_layer" if fetched else None,
        fetched_at=datetime.now(UTC) if fetched else None,
    )
    for i, t in enumerate(pages or [], 1):
        o.pages.append(OrderPage(page_no=i, text=t, text_source="text_layer"))
    return o


@pytest.fixture
def store(db_engine):
    wipe = text("TRUNCATE orders, fetch_log RESTART IDENTITY CASCADE")
    with db_engine.begin() as c:
        c.execute(wipe)
    with Session(db_engine) as s:
        a = order("RERA-GRG-101-2022", date(2023, 5, 2), [P1, P2])
        later = order("RERA-GRG-202-2024", date(2025, 3, 1), [P2])
        listed_only = order("RERA-GRG-303-2023", date(2024, 1, 5), fetched=False)
        twice_1 = order("RERA-GRG-404-2021", date(2022, 1, 1), [P2])
        twice_2 = order("RERA-GRG-404-2021", date(2022, 8, 1), [P2])
        s.add_all([a, later, listed_only, twice_1, twice_2])
        s.flush()
        s.add(
            CaseRecord(order_id=a.id, claim_type="delayed_possession", outcome="allowed", extracted_by="test")
        )
        s.commit()
        ids = {"a": a.id, "later": later.id, "listed": listed_only.id, "twice": twice_1.id}
    yield db_engine, ids
    with db_engine.begin() as c:
        c.execute(wipe)


GOOD_QUOTE = "The plea of force majeure is rejected. The complaint is allowed"


def check(engine, c, **kw):
    with Session(engine) as s:
        return verify_citation(s, c, before=kw.pop("before", CUTOFF), **kw)


def test_correct_citation_is_verified_with_stored_text(store):
    engine, ids = store
    v = check(
        engine,
        Citation(page_no=2, quote=GOOD_QUOTE, complaint_no="RERA-GRG-101-2022", claimed_outcome="allowed"),
    )
    assert v.verified and v.status == "verified" and v.reasons == []
    assert v.order_id == ids["a"] and v.decided_on == date(2023, 5, 2)
    assert P2[v.char_start : v.char_end] == v.stored_quote and v.match == "exact"


def test_rule1_invented_order_is_rejected(store):
    engine, _ = store
    assert (
        "not in the store"
        in check(engine, Citation(page_no=1, quote=GOOD_QUOTE, complaint_no="RERA-GRG-999-2022")).reasons[0]
    )
    assert (
        "not in the store" in check(engine, Citation(page_no=1, quote=GOOD_QUOTE, order_id=987654)).reasons[0]
    )


def test_rule2_id_and_complaint_number_must_agree(store):
    engine, ids = store
    v = check(
        engine, Citation(page_no=2, quote=GOOD_QUOTE, order_id=ids["a"], complaint_no="RERA-GRG-202-2024")
    )
    assert "not RERA-GRG-202-2024" in v.reasons[0]


def test_ambiguous_complaint_number_must_use_order_id(store):
    engine, ids = store
    v = check(engine, Citation(page_no=1, quote=GOOD_QUOTE, complaint_no="RERA-GRG-404-2021"))
    assert "has 2 decisions" in v.reasons[0]
    assert check(engine, Citation(page_no=1, quote=GOOD_QUOTE, order_id=ids["twice"])).verified


def test_rule3_order_without_stored_text_is_rejected(store):
    engine, _ = store
    v = check(engine, Citation(page_no=1, quote=GOOD_QUOTE, complaint_no="RERA-GRG-303-2023"))
    assert not v.verified and "not stored" in v.reasons[0]


def test_rule4_order_decided_after_the_cutoff_is_rejected(store):
    engine, _ = store
    v = check(engine, Citation(page_no=1, quote=GOOD_QUOTE, complaint_no="RERA-GRG-202-2024"))
    assert any("not before the cutoff" in r for r in v.reasons)
    # The same citation is fine for a case with a later cutoff.
    assert check(
        engine,
        Citation(page_no=1, quote=GOOD_QUOTE, complaint_no="RERA-GRG-202-2024"),
        before=date(2026, 1, 1),
    ).verified


def test_rule5_order_must_be_among_retrieved_orders(store):
    engine, ids = store
    c = Citation(page_no=2, quote=GOOD_QUOTE, order_id=ids["a"])
    assert check(engine, c, allowed_orders={ids["a"]}).verified
    assert "not among the orders retrieved" in check(engine, c, allowed_orders={ids["twice"]}).reasons[0]


def test_rule6_quote_must_be_on_the_cited_page(store):
    engine, ids = store
    wrong_page = check(engine, Citation(page_no=1, quote=GOOD_QUOTE, order_id=ids["a"]))
    assert wrong_page.reasons == ["quote not found on page 1"]
    no_page = check(engine, Citation(page_no=7, quote=GOOD_QUOTE, order_id=ids["a"]))
    assert no_page.reasons == ["page 7 does not exist in this order"]
    invented = check(
        engine,
        Citation(
            page_no=2, quote="The authority awarded damages of Rs. 10 lakh to the buyer", order_id=ids["a"]
        ),
    )
    assert invented.reasons == ["quote not found on page 2"]
    short = check(engine, Citation(page_no=2, quote="is allowed", order_id=ids["a"]))
    assert "too short" in short.reasons[0]


def test_rule6_small_ocr_difference_is_tolerated_and_stored_text_returned(store):
    engine, ids = store
    v = check(
        engine,
        Citation(
            page_no=2,
            quote="The plea of force majeur is rejected. The complaint is allowed",
            order_id=ids["a"],
        ),
    )
    assert v.verified and v.match.startswith("fuzzy:")
    assert "force majeure is rejected" in v.stored_quote


def test_rule7_claimed_outcome_must_match_the_record(store):
    engine, ids = store
    v = check(engine, Citation(page_no=2, quote=GOOD_QUOTE, order_id=ids["a"], claimed_outcome="dismissed"))
    assert v.reasons == ["says the outcome was dismissed, but the record says allowed"]
    no_record = check(
        engine, Citation(page_no=1, quote=GOOD_QUOTE, order_id=ids["twice"], claimed_outcome="allowed")
    )
    assert no_record.verified and "not checked" in no_record.notes[0]


def test_cutoff_is_required(store):
    engine, ids = store
    with Session(engine) as s, pytest.raises(TypeError):
        verify_citation(s, Citation(page_no=2, quote=GOOD_QUOTE, order_id=ids["a"]), before=None)


def test_verify_all_keeps_order_and_reports_each(store):
    engine, ids = store
    cites = [
        Citation(page_no=2, quote=GOOD_QUOTE, order_id=ids["a"]),
        Citation(page_no=1, quote=GOOD_QUOTE, complaint_no="RERA-GRG-999-2022"),
    ]
    with Session(engine) as s:
        verdicts = verify_all(s, cites, before=CUTOFF)
    assert [v.status for v in verdicts] == ["verified", "rejected"]


def test_rule6_a_changed_number_is_a_misquote_even_in_a_near_match(store):
    engine, ids = store
    # Long enough that one changed digit still aligns >= 90%: letters may differ, numbers may not.
    v = check(
        engine,
        Citation(
            page_no=1,
            quote="Complaint No. 107 of 2022 The respondent pleaded force majeure",
            order_id=ids["a"],
        ),
    )
    assert not v.verified
    assert "numbers in the quote (107, 2022) differ from the stored text (101, 2022)" in v.reasons[0]


def test_thousands_separators_do_not_count_as_different_numbers():
    from app.verifier.citations import _numbers

    assert _numbers("Rs. 72,00,000/- paid on 12.03.2018") == ["7200000", "12", "03", "2018"]
