"""Deleting cases and documents, the page picture with its highlight, facts that still need
checking, public figures and rate limits."""

from __future__ import annotations

import io
import uuid

from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.security import limiter
from app.buyer.page_view import normalised_with_map
from app.hearing.inputs import from_buyer_case
from app.main import app
from tests.conftest import make_user
from tests.pdf_factory import scanned_pdf, text_pdf
from tests.test_buyer import AGREEMENT_P1, AGREEMENT_P2, api, upload  # noqa: F401 - api is a fixture


def _case_with_facts(client):
    case = client.post("/api/v1/cases", json={"title": "Lifecycle", "is_demo": True}).json()
    doc = upload(client, case["id"], text_pdf([AGREEMENT_P1, AGREEMENT_P2])).json()
    assert client.post(f"/api/v1/cases/{case['id']}/facts/extract").status_code == 200
    return case["id"], doc["id"]


def _count(engine, table: str, case_id: str) -> int:
    with Session(engine) as s:
        return s.scalar(text(f"SELECT count(*) FROM {table} WHERE case_id = :c"), {"c": case_id})


# ── Deleting ──


def test_deleting_a_document_removes_its_file_text_chunks_and_facts(api, db_engine):  # noqa: F811
    client, _, uploads = api
    case_id, doc_id = _case_with_facts(client)
    stored = list((uploads / case_id).iterdir())
    assert len(stored) == 1 and _count(db_engine, "facts", case_id) > 0
    assert _count(db_engine, "case_document_chunks", case_id) > 0

    res = client.delete(f"/api/v1/cases/{case_id}/documents/{doc_id}")
    assert res.status_code == 200 and res.json()["facts_removed"] > 0
    assert not stored[0].exists()
    assert _count(db_engine, "facts", case_id) == 0
    assert _count(db_engine, "case_document_chunks", case_id) == 0
    assert _count(db_engine, "case_documents", case_id) == 0
    assert client.get(f"/api/v1/cases/{case_id}").json()["documents"] == []
    assert client.delete(f"/api/v1/cases/{case_id}/documents/{doc_id}").status_code == 404


def test_deleting_a_case_removes_everything_derived_from_it(api, db_engine):  # noqa: F811
    client, _, uploads = api
    case_id, _ = _case_with_facts(client)
    assert client.delete(f"/api/v1/cases/{case_id}").status_code == 200
    assert not (uploads / case_id).exists()
    for table in ("facts", "case_documents", "case_document_chunks", "case_answers", "hearing_runs"):
        assert _count(db_engine, table, case_id) == 0
    assert client.get(f"/api/v1/cases/{case_id}").status_code == 404


def test_another_user_cannot_delete_or_view_pages(api, db_engine):  # noqa: F811
    client, _, uploads = api
    case_id, doc_id = _case_with_facts(client)
    other = make_user(db_engine, "intruder@example.com")
    app.dependency_overrides[current_user] = lambda: other
    assert client.delete(f"/api/v1/cases/{case_id}").status_code == 404
    assert client.delete(f"/api/v1/cases/{case_id}/documents/{doc_id}").status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/pages/1/image").status_code == 404
    assert (
        client.get(f"/api/v1/cases/{case_id}/documents/{doc_id}/pages/1/highlight?start=0&end=5").status_code
        == 404
    )
    assert any((uploads / case_id).iterdir())  # nothing was removed


# ── The page as filed ──


def test_page_picture_and_highlight_for_a_text_pdf(api):  # noqa: F811
    client, _, _ = api
    case_id, doc_id = _case_with_facts(client)
    base = f"/api/v1/cases/{case_id}/documents/{doc_id}/pages"

    img = client.get(f"{base}/1/image")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    picture = Image.open(io.BytesIO(img.content))
    assert picture.format == "PNG" and picture.width >= 600

    fact = next(
        f for f in client.get(f"/api/v1/cases/{case_id}").json()["facts"] if f["key"] == "total_price"
    )
    hl = client.get(
        f"{base}/{fact['page_no']}/highlight?start={fact['char_start']}&end={fact['char_end']}"
    ).json()
    assert hl["rects"], "a text-layer page must give a highlight"
    for r in hl["rects"]:
        assert 0 <= r["x"] <= 1 and 0 <= r["y"] <= 1 and 0 < r["w"] <= 1 and 0 < r["h"] < 0.2
    # A different span of the same page lands somewhere else.
    other = client.get(f"{base}/{fact['page_no']}/highlight?start=0&end=20").json()["rects"]
    assert other and other != hl["rects"]

    assert client.get(f"{base}/9/image").status_code == 404
    assert client.get(f"{base}/1/highlight?start=5&end=999999").json()["rects"] is None


def test_scanned_page_has_a_picture_but_no_highlight(api, db_engine):  # noqa: F811
    """OCR text cannot be placed on the page for certain, so no highlight is offered."""
    client, _, uploads = api
    case = client.post("/api/v1/cases", json={"title": "Scan", "is_demo": True}).json()
    # Stored directly: this test has no OCR engine; what matters is the answer for an OCR page.
    pdf = scanned_pdf("Received Rs. 7,20,000")
    doc_id = str(uuid.uuid4())
    (uploads / case["id"]).mkdir(parents=True)
    (uploads / case["id"] / "scan.pdf").write_bytes(pdf)
    with Session(db_engine) as s:
        s.execute(
            text(
                "INSERT INTO case_documents (id, case_id, filename, kind, sha256, page_count, storage_key) "
                "VALUES (:d, :c, 'scan.pdf', 'receipt', :h, 1, :k)"
            ),
            {"d": doc_id, "c": case["id"], "h": "c" * 64, "k": f"{case['id']}/scan.pdf"},
        )
        s.execute(
            text(
                "INSERT INTO case_document_pages (document_id, page_no, text, text_source, ocr_engine) "
                "VALUES (:d, 1, 'Received Rs. 7,20,000', 'ocr', 'tesseract test')"
            ),
            {"d": doc_id},
        )
        s.commit()
    base = f"/api/v1/cases/{case['id']}/documents/{doc_id}/pages/1"
    assert client.get(f"{base}/image").status_code == 200
    assert client.get(f"{base}/highlight?start=0&end=8").json() == {"rects": None, "text_source": "ocr"}


def test_normalised_text_keeps_the_index_of_every_character():
    text_, index = normalised_with_map("  ab\r\ncd\r e \n")
    assert text_ == "ab\ncd\n e"
    assert [("  ab\r\ncd\r e \n")[i] for i in index] == ["a", "b", "\r", "c", "d", "\r", " ", "e"]


# ── Facts that still need checking ──


def test_a_fact_to_check_is_left_out_until_the_buyer_confirms_it(api, db_engine):  # noqa: F811
    client, _, _ = api
    case_id, _ = _case_with_facts(client)
    case = client.get(f"/api/v1/cases/{case_id}").json()
    assert case["facts_to_check"] == 0 and case["payments_total"] == "2160000.00"
    pay = next(f for f in case["facts"] if f["value"] == "2018-05-10;1440000.00")
    with Session(db_engine) as s:
        s.execute(text("UPDATE facts SET confidence = 'review' WHERE id = :i"), {"i": pay["id"]})
        s.execute(
            text("UPDATE facts SET confidence = 'review' WHERE case_id = :c AND key = 'possession_promised'"),
            {"c": case_id},
        )
        s.commit()

    case = client.get(f"/api/v1/cases/{case_id}").json()
    assert case["facts_to_check"] == 2 and case["payments_total"] == "720000.00"
    with Session(db_engine) as s:
        ci = from_buyer_case(s, uuid.UUID(case_id), "delayed_possession", __import__("datetime").date.today())
    assert ci.first("possession_promised") is None, "an unconfirmed fact must not reach the hearing"
    assert len(ci.payments) == 1
    assert client.get(f"/api/v1/cases/{case_id}/estimate").json().get("delay_months") is None

    assert client.post(f"/api/v1/cases/{case_id}/facts/{pay['id']}/confirm").status_code == 200
    case = client.get(f"/api/v1/cases/{case_id}").json()
    assert case["facts_to_check"] == 1 and case["payments_total"] == "2160000.00"
    with Session(db_engine) as s:
        ci = from_buyer_case(s, uuid.UUID(case_id), "delayed_possession", __import__("datetime").date.today())
    assert len(ci.payments) == 2


# ── Public figures and limits ──


def test_public_stats_count_the_order_store(api):  # noqa: F811
    client, _, _ = api
    app.dependency_overrides.pop(current_user, None)  # no sign-in needed
    out = client.get("/api/v1/stats").json()
    assert set(out) >= {"orders_listed", "orders_read", "passages", "outcome_records", "first_decided"}
    assert all(isinstance(out[k], int) for k in ("orders_listed", "orders_read", "passages"))


def test_expensive_routes_are_rate_limited_per_user(api):  # noqa: F811
    client, _, _ = api
    case_id, _ = _case_with_facts(client)
    limiter.reset()
    codes = [client.post(f"/api/v1/cases/{case_id}/facts/extract").status_code for _ in range(7)]
    assert codes[:6] == [200] * 6 and codes[6] == 429
    assert "Too many requests" in client.post(f"/api/v1/cases/{case_id}/facts/extract").json()["detail"]
