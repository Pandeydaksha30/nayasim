"""Step 5: buyer documents, verified facts, follow-up questions, cases API, privacy guard."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, InternalError
from sqlalchemy.orm import Session

from app.api import cases as cases_api
from app.auth.deps import current_user
from app.buyer import documents as documents_mod
from app.buyer.facts import FACT_SPECS, PaymentEvidence, ProposedBuyerFacts, verify_facts
from app.buyer.questions import questions_for, validate_answer
from app.config import settings
from app.db.models import Case, CaseDocument, CaseDocumentPage, Fact
from app.db.session import get_session
from app.extraction.order_fields import Evidence
from app.main import app
from tests.conftest import make_user
from tests.pdf_factory import text_pdf

AGREEMENT_P1 = (
    "AGREEMENT FOR SALE made on 2nd May 2018 between Arvant Infra Private Limited (the Promoter) "
    "and Ms. Ananya Mehra (the Allottee) for Apartment No. C-1204 in Skyline Residency. "
    "The Total Price of the Apartment is Rs. 72,00,000/- (Rupees Seventy-Two Lakh only)."
)
AGREEMENT_P2 = (
    "7.1 The Promoter shall hand over possession of the Apartment on or before 30th June 2021. "
    "Received with thanks Rs. 7,20,000/- by RTGS dated 12.03.2018 towards booking. "
    "Received with thanks Rs. 14,40,000/- by RTGS dated 10.05.2018 towards allotment."
)
PAGES = {1: AGREEMENT_P1, 2: AGREEMENT_P2}
QUALITY = {1: ("text_layer", None), 2: ("text_layer", None)}


def ev(value, quote, page):
    return Evidence(value=value, quote=quote, page_no=page)


def proposal(**kw) -> ProposedBuyerFacts:
    base = {k: Evidence() for k in FACT_SPECS}
    base.update(
        builder_name=ev(
            "Arvant Infra Private Limited", "between Arvant Infra Private Limited (the Promoter)", 1
        ),
        total_price=ev("7200000", "The Total Price of the Apartment is Rs. 72,00,000/-", 1),
        possession_promised=ev("2021-06-30", "possession of the Apartment on or before 30th June 2021", 2),
        payments=[
            PaymentEvidence(
                date="2018-03-12",
                amount="720000",
                quote="Received with thanks Rs. 7,20,000/- by RTGS dated 12.03.2018",
                page_no=2,
            ),
            PaymentEvidence(
                date="2018-05-10",
                amount="1440000",
                quote="Received with thanks Rs. 14,40,000/- by RTGS dated 10.05.2018",
                page_no=2,
            ),
        ],
    )
    base.update(kw)
    return ProposedBuyerFacts(**base)


# ── Verification ──


def test_verified_facts_quote_the_stored_page_exactly():
    result = verify_facts(proposal(), PAGES, QUALITY)
    assert result.rejected == []
    by_key = {f.key: f for f in result.facts}
    assert by_key["total_price"].value == "7200000.00"
    assert by_key["possession_promised"].value == "2021-06-30"
    for f in result.facts:
        assert PAGES[f.page_no][f.char_start : f.char_end] == f.quote
        assert f.confidence == "high"
    assert [f.value for f in result.facts if f.key == "payment"] == [
        "2018-03-12;720000.00",
        "2018-05-10;1440000.00",
    ]


def test_payment_amount_not_in_text_is_rejected():
    bad = PaymentEvidence(
        date="2018-03-12",
        amount="750000",
        quote="Received with thanks Rs. 7,20,000/- by RTGS dated 12.03.2018",
        page_no=2,
    )
    result = verify_facts(proposal(payments=[bad]), PAGES, QUALITY)
    assert not [f for f in result.facts if f.key == "payment"]
    assert result.rejected[0]["reason"] == "payment amount not readable from the stored text"


def test_name_that_is_not_in_the_quote_is_rejected():
    result = verify_facts(
        proposal(
            builder_name=ev("Skyline Builders Ltd", "between Arvant Infra Private Limited (the Promoter)", 1)
        ),
        PAGES,
        QUALITY,
    )
    assert "builder_name" not in {f.key for f in result.facts}
    assert result.rejected[0]["reason"] == "value not found in the stored text"


def test_duplicate_payment_is_kept_once():
    p = proposal()
    result = verify_facts(proposal(payments=p.payments + [p.payments[0]]), PAGES, QUALITY)
    assert len([f for f in result.facts if f.key == "payment"]) == 2


def test_low_ocr_or_near_match_marks_fact_for_review():
    weak = {1: ("ocr", 65.0), 2: ("text_layer", None)}
    result = verify_facts(proposal(), PAGES, weak)
    assert {f.key: f.confidence for f in result.facts}["total_price"] == "review"
    near = proposal(
        possession_promised=ev("2021-06-30", "possession of the Apartment on or before 30th Jume 2021", 2)
    )  # one-letter OCR slip
    got = {f.key: f for f in verify_facts(near, PAGES, QUALITY).facts}["possession_promised"]
    assert got.confidence == "review" and "30th June 2021" in got.quote


# ── Questions ──


def test_questions_follow_the_facts():
    ids = {q.id for q in questions_for({})}
    assert {"agreement_missing", "payments_missing", "relief", "offer_of_possession"} <= ids
    ids = {
        q.id
        for q in questions_for(
            {"possession_promised": ["2021-06-30"], "payment": ["x"], "escalation_demand": ["144000.00"]}
        )
    }
    assert "agreement_missing" not in ids and "payments_missing" not in ids
    assert {"payments_complete", "escalation_paid"} <= ids


def test_answers_must_be_one_of_the_options():
    validate_answer("relief", "Withdraw and claim a refund")
    with pytest.raises(ValueError):
        validate_answer("relief", "maybe")
    with pytest.raises(KeyError):
        validate_answer("not_a_question", "No")


# ── API with the test database ──


class StandIn:
    name = "stand-in"

    def __init__(self):
        self.calls = 0

    def propose(self, prompt, schema):
        self.calls += 1
        assert schema is ProposedBuyerFacts and "=== PAGE 1 ===" in prompt
        return proposal()


@pytest.fixture
def api(db_engine, tmp_path, monkeypatch):
    wipe = text("TRUNCATE cases RESTART IDENTITY CASCADE")
    with db_engine.begin() as c:
        c.execute(wipe)

    def session_override():
        with Session(db_engine) as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    stand_in = StandIn()
    monkeypatch.setattr(documents_mod, "UPLOAD_ROOT", tmp_path)
    owner = make_user(db_engine)
    monkeypatch.setattr(settings, "allow_demo_cases", True)  # these tests use demo cases on purpose
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[current_user] = lambda: owner
    app.dependency_overrides[cases_api.get_ocr] = lambda: None
    app.dependency_overrides[cases_api.get_fact_extractor] = lambda: stand_in
    yield TestClient(app), stand_in, tmp_path
    app.dependency_overrides.clear()
    with db_engine.begin() as c:
        c.execute(wipe)


def upload(client, case_id, pdf: bytes, name="agreement.pdf", kind="agreement"):
    return client.post(
        f"/api/v1/cases/{case_id}/documents",
        data={"kind": kind},
        files={"file": (name, pdf, "application/pdf")},
    )


def test_demo_case_upload_extract_and_answer(api):
    client, stand_in, root = api
    case = client.post("/api/v1/cases", json={"title": "Demo v. Builder", "is_demo": True}).json()
    pdf = text_pdf([AGREEMENT_P1, AGREEMENT_P2])

    res = upload(client, case["id"], pdf)
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["page_count"] == 2 and not doc["duplicate"]
    assert any(p.suffix == ".pdf" for p in (root / case["id"]).iterdir())
    assert upload(client, case["id"], pdf).json()["duplicate"] is True

    summary = client.post(f"/api/v1/cases/{case['id']}/facts/extract").json()
    assert summary["facts"] >= 5 and summary["errors"] == []

    full = client.get(f"/api/v1/cases/{case['id']}").json()
    assert full["payments_total"] == "2160000.00"
    for f in full["facts"]:
        page = client.get(
            f"/api/v1/cases/{case['id']}/documents/{f['document_id']}/pages/{f['page_no']}"
        ).json()
        assert page["text"][f["char_start"] : f["char_end"]] == f["quote"]
    q_ids = {q["id"] for q in full["questions"]}
    assert "agreement_missing" not in q_ids and "offer_of_possession" in q_ids

    res = client.put(
        f"/api/v1/cases/{case['id']}/answers/relief", json={"answer": "Withdraw and claim a refund"}
    )
    assert res.status_code == 200
    assert {q["id"]: q["answer"] for q in res.json()["questions"]}["relief"] == "Withdraw and claim a refund"
    assert client.put(f"/api/v1/cases/{case['id']}/answers/relief", json={"answer": "x"}).status_code == 422

    fact_id = full["facts"][0]["id"]
    assert client.post(f"/api/v1/cases/{case['id']}/facts/{fact_id}/confirm").json()["confirmed"] is True


def test_real_case_documents_are_not_sent_to_a_retaining_model(api):
    client, stand_in, _ = api
    case = client.post("/api/v1/cases", json={"title": "Real buyer"}).json()
    assert upload(client, case["id"], text_pdf([AGREEMENT_P1])).status_code == 201
    res = client.post(f"/api/v1/cases/{case['id']}/facts/extract")
    assert res.status_code == 403
    assert "not sent" in res.json()["detail"]
    assert stand_in.calls == 0


def test_upload_rejects_non_documents_and_unknown_kinds(api):
    client, _, _ = api
    case = client.post("/api/v1/cases", json={"title": "x", "is_demo": True}).json()
    res = client.post(
        f"/api/v1/cases/{case['id']}/documents",
        data={"kind": "agreement"},
        files={"file": ("a.pdf", b"<html>not a pdf</html>", "application/pdf")},
    )
    assert res.status_code == 422 and "PDF, PNG and JPG" in res.json()["detail"]
    assert upload(client, case["id"], text_pdf([AGREEMENT_P1]), kind="selfie").status_code == 422
    assert client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000").status_code == 404


def test_database_rejects_a_fact_whose_quote_is_not_the_page_text(db: Session):
    case = Case(title="t", claim_type="refund", is_demo=True)
    doc = CaseDocument(filename="a.pdf", kind="agreement", sha256="b" * 64, page_count=1, storage_key="k")
    doc.pages.append(CaseDocumentPage(page_no=1, text=AGREEMENT_P1, text_source="text_layer"))
    case.documents.append(doc)
    db.add(case)
    db.flush()
    start = AGREEMENT_P1.index("Rs. 72,00,000")
    ok = Fact(
        case_id=case.id,
        document_id=doc.id,
        key="total_price",
        label="Total price",
        value="7200000.00",
        page_no=1,
        char_start=start,
        char_end=start + 13,
        quote="Rs. 72,00,000",
        confidence="high",
    )
    db.add(ok)
    db.flush()
    bad = Fact(
        case_id=case.id,
        document_id=doc.id,
        key="total_price",
        label="Total price",
        value="7500000.00",
        page_no=1,
        char_start=start,
        char_end=start + 13,
        quote="Rs. 75,00,000",
        confidence="high",
    )
    db.add(bad)
    with pytest.raises((IntegrityError, InternalError)):
        db.flush()


def test_case_list_shows_counts(api):
    client, _, _ = api
    a = client.post("/api/v1/cases", json={"title": "First", "is_demo": True}).json()
    upload(client, a["id"], text_pdf([AGREEMENT_P1, AGREEMENT_P2]))
    client.post(f"/api/v1/cases/{a['id']}/facts/extract")
    client.post("/api/v1/cases", json={"title": "Second"})
    listed = client.get("/api/v1/cases").json()
    assert [c["title"] for c in listed] == ["Second", "First"]
    first = listed[1]
    assert first["documents"] == 1 and first["facts"] >= 5 and first["is_demo"] is True


def test_oversized_upload_is_refused_without_reading_it_all(api, monkeypatch):
    client, _, _ = api
    monkeypatch.setattr(documents_mod, "MAX_BYTES", 1000)
    case = client.post("/api/v1/cases", json={"title": "x", "is_demo": True}).json()
    res = upload(client, case["id"], text_pdf([AGREEMENT_P1 * 5]))
    assert res.status_code == 413 and "25 MB" in res.json()["detail"]


def test_no_transaction_is_open_while_the_model_reads_documents(db_engine, tmp_path, monkeypatch):
    from app.buyer.facts import extract_case_facts

    monkeypatch.setattr(documents_mod, "UPLOAD_ROOT", tmp_path)
    seen = []
    with Session(db_engine) as s:
        case = Case(title="t", claim_type="refund", is_demo=True)
        s.add(case)
        s.flush()
        documents_mod.store_document(
            s, case.id, "a.pdf", "agreement", text_pdf([AGREEMENT_P1, AGREEMENT_P2]), None
        )
        documents_mod.store_document(s, case.id, "b.pdf", "receipt", text_pdf([AGREEMENT_P2]), None)
        s.commit()

        class Watching(StandIn):
            def propose(self, prompt, schema):
                seen.append(s.in_transaction())
                return super().propose(prompt, schema)

        summary = extract_case_facts(s, case.id, Watching())
        assert summary["documents"] == 2 and not summary["errors"]
        s.execute(text("DELETE FROM cases WHERE id = :i"), {"i": case.id})
        s.commit()
    assert seen == [False, False]


def test_upload_over_page_limit_is_refused_before_ocr(api, monkeypatch):
    client, _, _ = api
    monkeypatch.setattr(documents_mod, "MAX_PAGES", 2)
    case = client.post("/api/v1/cases", json={"title": "Long"}).json()
    r = upload(client, case["id"], text_pdf([AGREEMENT_P1, AGREEMENT_P2, AGREEMENT_P1]))
    assert r.status_code == 422 and "limit is 2" in r.json()["detail"]
    assert client.get(f"/api/v1/cases/{case['id']}").json()["documents"] == []


def test_uploads_beyond_parallel_limit_get_busy_answer(api, monkeypatch):
    import threading

    client, _, _ = api
    monkeypatch.setattr(cases_api, "_upload_slots", threading.BoundedSemaphore(1))
    cases_api._upload_slots.acquire()  # another upload is being read
    case = client.post("/api/v1/cases", json={"title": "Busy"}).json()
    r = upload(client, case["id"], text_pdf([AGREEMENT_P1]))
    assert r.status_code == 503
    cases_api._upload_slots.release()
    assert upload(client, case["id"], text_pdf([AGREEMENT_P1])).status_code == 201
