"""Step 6: search with a mandatory decision-date cutoff."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Order, OrderChunk, OrderPage
from app.retrieval import search as search_mod
from app.retrieval.embedder import HashingEmbedder
from app.retrieval.search import CutoffLeak, keyword_query, search

EMB = HashingEmbedder()

ORDERS = [
    # complaint, decided, chunks
    (
        "RERA-GRG-1-2023",
        date(2023, 3, 1),
        [
            "The promoter failed to deliver possession; force majeure plea rejected and "
            "delay interest allowed.",
            "Interest at the prescribed rate shall be paid for every month of delay till possession.",
            "The respondent pleaded force majeure due to NGT construction bans.",
        ],
    ),
    (
        "RERA-GRG-2-2024",
        date(2024, 6, 1),
        [
            "Refund of the entire amount paid with interest is allowed as the allottee withdrew.",
        ],
    ),
    (
        "RERA-GRG-3-2025",
        date(2025, 2, 1),
        [
            "Delay possession charges allowed; force majeure plea rejected (decided after the cutoff).",
        ],
    ),
    (
        "RERA-GRG-4-2023",
        date(2023, 9, 1),
        [
            "Holding charges cannot be levied; maintenance deposit refundable.",
        ],
    ),
]


@pytest.fixture
def corpus(db_engine):
    wipe = text("TRUNCATE orders, fetch_log RESTART IDENTITY CASCADE")
    with db_engine.begin() as c:
        c.execute(wipe)
    with Session(db_engine) as s:
        for no, decided, chunks in ORDERS:
            o = Order(
                source="hrera_gurugram",
                complaint_no=no,
                case_type="HRERA Complaints",
                decided_on=decided,
                pdf_url="u",
                pdf_sha256="c" * 64,
                page_count=1,
                text_source="text_layer",
                fetched_at=datetime.now(UTC),
            )
            page = "\n\n".join(chunks)
            o.pages.append(OrderPage(page_no=1, text=page, text_source="text_layer"))
            s.add(o)
            s.flush()
            for chunk, vec in zip(chunks, EMB.embed_documents(chunks), strict=True):
                start = page.index(chunk)
                s.add(
                    OrderChunk(
                        order_id=o.id,
                        page_no=1,
                        char_start=start,
                        char_end=start + len(chunk),
                        text=chunk,
                        embedding=vec,
                        embedding_model=EMB.name,
                    )
                )
        s.commit()
    yield db_engine
    with db_engine.begin() as c:
        c.execute(wipe)


CUTOFF = date(2025, 1, 1)


def test_keyword_query_ors_content_words():
    assert keyword_query("The force majeure plea of the promoter") == "force or majeure or plea or promoter"
    assert keyword_query("the of and") == ""


def test_cutoff_is_required(corpus):
    with Session(corpus) as s, pytest.raises(TypeError, match="cutoff"):
        search(s, "force majeure", before=None)


def test_orders_on_or_after_the_cutoff_are_never_returned(corpus):
    with Session(corpus) as s:
        for emb in (None, EMB):
            res = search(s, "force majeure plea rejected delay possession", before=CUTOFF, embedder=emb, k=20)
            assert res.hits, emb
            assert all(h.decided_on < CUTOFF for h in res.hits)
            assert "RERA-GRG-3-2025" not in {h.complaint_no for h in res.hits}
        # Move the cutoff past it and the 2025 order becomes searchable.
        later = search(s, "force majeure plea rejected", before=date(2026, 1, 1), embedder=EMB, k=20)
        assert "RERA-GRG-3-2025" in {h.complaint_no for h in later.hits}


def test_cutoff_is_exclusive(corpus):
    with Session(corpus) as s:
        res = search(s, "refund withdrew", before=date(2024, 6, 1), k=20)
        assert "RERA-GRG-2-2024" not in {h.complaint_no for h in res.hits}


def test_english_stemming_matches_word_forms(corpus):
    with Session(corpus) as s:
        res = search(s, "possessed", before=CUTOFF)
        assert any("possession" in h.text for h in res.hits)


def test_hybrid_mode_and_vector_only_match(corpus):
    with Session(corpus) as s:
        res = search(s, "holding maintenance", before=CUTOFF, embedder=EMB)
        assert res.mode == "hybrid"
        top = res.hits[0]
        assert top.complaint_no == "RERA-GRG-4-2023" and top.keyword_rank and top.vector_rank


class _OtherModel(HashingEmbedder):
    """Same vectors, different model name: its vectors must not be compared with stored ones."""

    def __init__(self):
        super().__init__()
        self.name = "some-other-model"


def test_keyword_only_when_model_has_no_embeddings(corpus):
    with Session(corpus) as s:
        res = search(s, "force majeure", before=CUTOFF, embedder=_OtherModel())
        assert res.mode == "keyword" and "no stored embeddings" in res.notes[0]


def test_at_most_two_chunks_per_order(corpus):
    with Session(corpus) as s:
        res = search(s, "force majeure interest delay possession promoter", before=CUTOFF, embedder=EMB, k=20)
        counts: dict[str, int] = {}
        for h in res.hits:
            counts[h.complaint_no] = counts.get(h.complaint_no, 0) + 1
        assert max(counts.values()) <= 2


def test_hits_point_at_the_stored_page_text(corpus):
    with Session(corpus) as s:
        res = search(s, "prescribed rate", before=CUTOFF)
        h = res.hits[0]
        page = s.scalar(
            text("SELECT text FROM order_pages WHERE order_id = :o AND page_no = :p"),
            {"o": h.order_id, "p": h.page_no},
        )
        assert page[h.char_start : h.char_end] == h.text


def test_a_leaking_hit_raises_instead_of_being_dropped(corpus, monkeypatch):
    with Session(corpus) as s:
        later_chunk = s.scalar(
            text(
                "SELECT c.id FROM order_chunks c JOIN orders o ON o.id = c.order_id WHERE o.decided_on >= :d"
            ),
            {"d": CUTOFF},
        )
        monkeypatch.setattr(search_mod, "keyword_ranks", lambda *a, **k: [later_chunk])
        with pytest.raises(CutoffLeak):
            search(s, "anything", before=CUTOFF)
