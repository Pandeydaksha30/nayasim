"""Search and question answering over a case's own documents (app/api/rag.py)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.hearing import get_hearing_llm
from app.auth.deps import current_user
from app.main import app
from app.rag.answer import NOT_ENOUGH, DocAnswer, DocCite, check_citations
from app.retrieval.case_search import Passage, search_case
from tests.conftest import make_user
from tests.pdf_factory import text_pdf
from tests.test_buyer import AGREEMENT_P1, AGREEMENT_P2, api, upload  # noqa: F401  (api is a fixture)

OTHER_DOC = (
    "LEASE DEED between Zenith Estates and Mr. Kabir Rao for Shop No. 9 in Sector 14 market, "
    "monthly rent Rs. 45,000/- payable on the fifth day of every calendar month."
)


class Scripted:
    """Stand-in model: answers with what the test gives it, and records the prompt it was sent."""

    name = "scripted"

    def __init__(self, out: DocAnswer | Exception):
        self.out = out
        self.prompts: list[str] = []

    def propose(self, prompt, schema):
        self.prompts.append(prompt)
        assert schema is DocAnswer
        if isinstance(self.out, Exception):
            raise self.out
        return self.out


def use_model(model) -> None:
    app.dependency_overrides[get_hearing_llm] = lambda: model


def demo_case(client, title="Demo") -> str:
    case = client.post("/api/v1/cases", json={"title": title, "is_demo": True}).json()
    assert upload(client, case["id"], text_pdf([AGREEMENT_P1, AGREEMENT_P2])).status_code == 201
    return case["id"]


def test_upload_creates_chunks_with_document_page_and_embedding(api, db_engine):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    with Session(db_engine) as s:
        rows = s.execute(
            text("""SELECT page_no, text, embedding IS NOT NULL, embedding_model, case_id::text
                    FROM case_document_chunks ORDER BY page_no""")
        ).all()
    assert [r[0] for r in rows] == [1, 2]
    assert "Arvant Infra" in rows[0][1] and "30th June 2021" in rows[1][1]
    assert all(r[2] and r[3] == "hashing-384" and r[4] == case_id for r in rows)


def test_passages_come_only_from_this_case_and_need_no_model(api):  # noqa: F811
    client, _, _ = api
    mine = demo_case(client)
    other = client.post("/api/v1/cases", json={"title": "Other"}).json()["id"]
    assert upload(client, other, text_pdf([OTHER_DOC]), name="lease.pdf", kind="other").status_code == 201
    res = client.get(f"/api/v1/cases/{mine}/passages", params={"q": "possession of the apartment"})
    assert res.status_code == 200, res.text
    hits = res.json()["hits"]
    assert {h["page_no"] for h in hits} == {1, 2} and all(h["filename"] == "agreement.pdf" for h in hits)
    assert all("Zenith" not in h["text"] for h in hits)
    # A private (non-demo) case can be searched: nothing leaves the server.
    res = client.get(f"/api/v1/cases/{other}/passages", params={"q": "monthly rent for the shop"})
    assert res.status_code == 200 and "Zenith" in res.json()["hits"][0]["text"]
    # Words that exist only in the other case find nothing relevant here by keyword.
    assert client.get(f"/api/v1/cases/{mine}/passages", params={"q": "ab"}).status_code == 422


def test_another_user_cannot_search_ask_or_list(api, db_engine):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    use_model(Scripted(DocAnswer(insufficient=True, answer="")))
    intruder = make_user(db_engine, "intruder@example.com")
    app.dependency_overrides[current_user] = lambda: intruder
    assert client.get(f"/api/v1/cases/{case_id}/passages", params={"q": "possession"}).status_code == 404
    assert (
        client.post(f"/api/v1/cases/{case_id}/ask", json={"question": "When is possession?"}).status_code
        == 404
    )
    assert client.get(f"/api/v1/cases/{case_id}/questions").status_code == 404
    del app.dependency_overrides[current_user]
    assert client.get(f"/api/v1/cases/{case_id}/passages", params={"q": "possession"}).status_code == 401


def test_search_function_never_returns_another_cases_chunk(api, db_engine):  # noqa: F811
    client, _, _ = api
    mine = demo_case(client)
    other = client.post("/api/v1/cases", json={"title": "Other"}).json()["id"]
    assert upload(client, other, text_pdf([OTHER_DOC]), name="lease.pdf", kind="other").status_code == 201
    with Session(db_engine) as s:
        hits, _ = search_case(s, uuid.UUID(mine), "Zenith Estates lease deed shop monthly rent", None, k=10)
        assert all(h.filename == "agreement.pdf" for h in hits)
        with pytest.raises(TypeError):
            search_case(s, mine, "rent", None)  # a string is refused: the id must be a real UUID


def test_answer_is_shown_only_with_a_citation_found_in_the_document(api):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    model = Scripted(
        DocAnswer(
            insufficient=False,
            answer="Possession was promised by 30 June 2021.",
            citations=[
                DocCite(ref="D1", quote="hand over possession of the Apartment on or before 30th June 2021"),
                DocCite(ref="D1", quote="possession shall be given whenever the Promoter likes"),
                DocCite(ref="D9", quote="hand over possession of the Apartment"),
            ],
        )
    )
    use_model(model)
    res = client.post(f"/api/v1/cases/{case_id}/ask", json={"question": "When was possession promised?"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["insufficient"] is False and "30 June 2021" in body["answer"]
    assert len(body["citations"]) == 1
    cite = body["citations"][0]
    assert cite["status"] == "verified" and cite["page_no"] == 2 and cite["filename"] == "agreement.pdf"
    assert "30th June 2021" in cite["quote"]
    assert {r["reason"] for r in body["rejected_citations"]} == {
        "quote not found in the passage",
        "names a passage that was not provided",
    }
    # The model saw only this case's passages, labelled, and the question.
    assert (
        "[D1] agreement.pdf, page 2" in model.prompts[0]
        and "When was possession promised?" in model.prompts[0]
    )
    history = client.get(f"/api/v1/cases/{case_id}/questions").json()
    assert (
        history[0]["question"] == "When was possession promised?" and "text" not in history[0]["retrieved"][0]
    )


def test_unsupported_or_insufficient_answers_are_replaced(api):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    invented = DocAnswer(
        insufficient=False,
        answer="The penalty is Rs. 9 crore.",
        citations=[DocCite(ref="D1", quote="the Promoter shall pay a penalty of Rs. 9 crore")],
    )
    use_model(Scripted(invented))
    body = client.post(
        f"/api/v1/cases/{case_id}/ask", json={"question": "What is the penalty amount?"}
    ).json()
    assert (
        body["insufficient"] is True and body["answer"] == NOT_ENOUGH and "9 crore" not in str(body["answer"])
    )
    assert body["reason"] == "no citation could be verified against the documents"
    use_model(Scripted(DocAnswer(insufficient=True, answer="I cannot tell.")))
    body = client.post(f"/api/v1/cases/{case_id}/ask", json={"question": "Who is the architect?"}).json()
    assert body["insufficient"] is True and body["citations"] == []


def test_private_case_is_not_sent_to_the_model_and_failures_are_reported(api):  # noqa: F811
    client, _, _ = api
    private = client.post("/api/v1/cases", json={"title": "Real"}).json()["id"]
    upload(client, private, text_pdf([AGREEMENT_P1]))
    model = Scripted(DocAnswer(insufficient=True, answer=""))
    use_model(model)
    res = client.post(f"/api/v1/cases/{private}/ask", json={"question": "What is the total price?"})
    assert res.status_code == 403 and model.prompts == []
    case_id = demo_case(client, "Demo 2")
    use_model(Scripted(RuntimeError("model unavailable")))
    res = client.post(f"/api/v1/cases/{case_id}/ask", json={"question": "What is the total price?"})
    assert res.status_code == 503 and "try again" in res.json()["detail"]
    assert client.post(f"/api/v1/cases/{case_id}/ask", json={"question": "hi"}).status_code == 422


def test_chunks_are_deleted_with_the_case(api, db_engine):  # noqa: F811
    client, _, _ = api
    demo_case(client)
    with db_engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM case_document_chunks")).scalar() > 0
        c.execute(text("DELETE FROM cases"))
        assert c.execute(text("SELECT count(*) FROM case_document_chunks")).scalar() == 0


def test_citation_check_uses_the_stored_text_not_the_models_wording():
    p = Passage(
        1, uuid.uuid4(), "a.pdf", "agreement", 3, 100, 200, "The Total Price is Rs. 72,00,000/- only.", 1.0
    )
    good, bad = check_citations([DocCite(ref="[d1]", quote="the total   price is rs. 72,00,000/-")], [p])
    assert (
        not bad and good[0]["quote"] == "The Total Price is Rs. 72,00,000/-" and good[0]["char_start"] == 100
    )
    good, bad = check_citations([DocCite(ref="D1", quote="The Total Price is Rs. 27,00,000/- only")], [p])
    assert not good and bad
