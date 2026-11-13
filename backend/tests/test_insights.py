"""Outcome estimate, complaint draft, order search and classifier demo (app/api/insights.py)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import numpy as np
from sqlalchemy.orm import Session

from app.api import insights as insights_api
from app.api.hearing import get_search_embedder
from app.auth.deps import current_user
from app.db.models import CaseRecord, HearingRun, Order
from app.insights.draft import _rs
from app.insights.estimate import outcome_estimate
from app.main import app
from tests.pdf_factory import text_pdf
from tests.test_buyer import AGREEMENT_P1, AGREEMENT_P2, api, upload  # noqa: F401  (api is a fixture)


def test_rupee_amounts_use_indian_grouping():
    assert _rs("3240000.00") == "Rs. 32,40,000/-"
    assert _rs("720000") == "Rs. 7,20,000/-"
    assert _rs("999") == "Rs. 999/-"
    assert _rs("12345678") == "Rs. 1,23,45,678/-"


def test_draft_of_an_empty_case_leaves_blanks_and_lists_what_is_missing(api):  # noqa: F811
    client, _, _ = api
    case = client.post("/api/v1/cases", json={"title": "Empty"}).json()
    d = client.get(f"/api/v1/cases/{case['id']}/draft")
    assert d.status_code == 200, d.text
    body = d.json()
    assert "Promised date of possession" in body["missing"]
    assert "[Promised date of possession: not found" in body["text"]
    assert body["verified_citations"] == 0 and body["based_on_hearing"] is None
    assert "HARYANA REAL ESTATE REGULATORY AUTHORITY" in body["header"][0]


def test_draft_uses_only_verified_facts_and_verified_citations(api, db_engine):  # noqa: F811
    client, _, _ = api
    case = client.post("/api/v1/cases", json={"title": "Demo", "is_demo": True}).json()
    upload(client, case["id"], text_pdf([AGREEMENT_P1, AGREEMENT_P2]))
    client.post(f"/api/v1/cases/{case['id']}/facts/extract")
    good = {
        "status": "verified",
        "order_id": 1,
        "complaint_no": "RERA-GRG-1-2020",
        "decided_on": "2021-03-04",
        "page_no": 7,
        "quote": "the complainant is entitled to delay possession charges",
    }
    bad = {**good, "status": "rejected", "quote": "an invented sentence", "complaint_no": "RERA-GRG-9-2020"}
    result = {
        "arguments": {"buyer": [{"citations": [good, bad]}], "builder": [], "removed": []},
        "award": {
            "available": True,
            "rate_pct": "10.900",
            "rate_basis": "median of 3 rate(s)",
            "delay_interest": "500000.00",
            "refund_total": "3000000.00",
            "as_of": "2026-11-12",
        },
        "judge": {"weak_points": [{"title": "Proof of payment", "fix": "Attach bank entries."}]},
    }
    with Session(db_engine) as s:
        s.add(
            HearingRun(
                case_id=case["id"],
                cutoff=date(2026, 11, 12),
                models="t",
                status="completed",
                result=result,
                finished_at=datetime.now(UTC),
            )
        )
        s.commit()
    body = client.get(f"/api/v1/cases/{case['id']}/draft").json()
    text = body["text"]
    assert "Arvant Infra Private Limited" in text and "30 June 2021" in text
    assert "Rs. 21,60,000/- in 2 payment(s)" in text
    assert "agreement.pdf, page 2" in text
    assert "RERA-GRG-1-2020" in text and "entitled to delay possession charges" in text
    assert "an invented sentence" not in text and "RERA-GRG-9-2020" not in text
    assert "Rs. 5,00,000/-" in text and body["verified_citations"] == 1
    assert any("Proof of payment" in n["label"] for n in body["notes"])
    assert "Promised date of possession" not in body["missing"]


def test_estimate_counts_past_orders_with_the_same_claim_and_delay(db: Session):
    assert outcome_estimate(db, "refund", None, date(2026, 1, 1))["available"] is False
    for i, outcome in enumerate(["allowed", "allowed", "allowed", "dismissed"]):
        o = Order(
            source="hrera_gurugram",
            case_type="HRERA Complaints",
            pdf_url=f"https://example.test/{i}.pdf",
            complaint_no=f"RERA-GRG-{i}-2020",
            decided_on=date(2022, 1, 1),
        )
        db.add(o)
        db.flush()
        db.add(
            CaseRecord(
                order_id=o.id,
                claim_type="refund",
                outcome=outcome,
                possession_due=date(2019, 6, 1),
                extracted_by="test",
            )
        )
    db.flush()
    est = outcome_estimate(db, "refund", date(2023, 6, 1), date(2026, 1, 1))
    assert est["available"] and est["predicted"] == "allowed"
    assert est["counts"] == {"allowed": 3, "dismissed": 1} and est["orders_used"] == 4
    assert est["delay_band"] == "2 to 4 years" and est["measured"]["accuracy_pct"] == 72.9
    # A claim type never seen falls back to all past orders, and says so.
    other = outcome_estimate(db, "other", None, date(2026, 1, 1))
    assert "all past orders" in other["basis"]


def test_estimate_endpoint_and_search_need_a_login_and_validate_input(api):  # noqa: F811
    client, _, _ = api
    app.dependency_overrides[get_search_embedder] = lambda: None
    case = client.post("/api/v1/cases", json={"title": "x"}).json()
    assert client.get(f"/api/v1/cases/{case['id']}/estimate").status_code == 200
    assert client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000/estimate").status_code == 404
    assert client.get("/api/v1/search/orders", params={"q": "ab"}).status_code == 422
    res = client.get("/api/v1/search/orders", params={"q": "refund with interest section 18"})
    assert res.status_code == 200 and res.json()["mode"] == "keyword"
    del app.dependency_overrides[current_user]
    assert client.get("/api/v1/search/orders", params={"q": "refund with interest"}).status_code == 401
    assert client.get(f"/api/v1/cases/{case['id']}/draft").status_code == 401


class FakeModel:
    classes_ = np.array(["delayed_possession", "other", "refund"])

    def predict_proba(self, texts):
        return np.array([[0.7, 0.1, 0.2]] * len(texts))


def test_classifier_demo_uses_the_relief_rule_first_and_reports_measured_accuracy(api, monkeypatch):  # noqa: F811
    client, _, _ = api
    monkeypatch.setattr(insights_api, "_model", lambda task: FakeModel())
    filler = "The complainant booked a unit in the project of the respondent. " * 5
    refund = (
        filler + "C. Relief sought by the complainant: Direct the respondent to refund the entire amount."
    )
    out = client.post("/api/v1/predictions/order-text", json={"text": refund}).json()
    assert out["claim_type"]["label"] == "refund" and out["claim_type"]["decided_by"] == "relief-section rule"
    assert out["claim_type"]["measured"]["accuracy_pct"] == 74.3 and "caveat" in out
    plain = client.post("/api/v1/predictions/order-text", json={"text": filler}).json()
    assert plain["claim_type"]["label"] == "delayed_possession"
    assert plain["claim_type"]["decided_by"].startswith("TF-IDF")
    assert client.post("/api/v1/predictions/order-text", json={"text": "short"}).status_code == 422
