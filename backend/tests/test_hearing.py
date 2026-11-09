"""Step 8: hearing graph, citation gate, statistics and award, privacy, API."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api import hearing as hearing_api
from app.auth.deps import current_user
from app.buyer.facts import PrivateDataBlocked
from app.db.models import (
    Case,
    CaseDocument,
    CaseDocumentPage,
    CaseRecord,
    Fact,
    HearingRun,
    Order,
    OrderChunk,
    OrderPage,
)
from app.db.session import get_session
from app.hearing import agents
from app.hearing.inputs import CaseInput, Precedent
from app.hearing.runner import HearingNotPossible, run_case_hearing
from app.hearing.stats import award, outcome_shares, wilson
from app.main import app
from tests.conftest import make_user

CUTOFF = date(2025, 1, 1)


# ── Statistics and award (pure) ──


def prec(outcome, rate=None, n=1):
    return Precedent(
        f"P{n}", n, f"C{n}", date(2023, 1, 1), outcome, Decimal(rate) if rate else None, [(1, "x")]
    )


def test_wilson_interval_matches_known_values():
    lo, hi = wilson(8, 10)
    assert (round(lo, 3), round(hi, 3)) == (0.541, 0.931)
    assert wilson(0, 0) == (0.0, 1.0)


def test_outcome_shares_need_enough_records():
    few = outcome_shares([prec("allowed", n=i) for i in range(1, 5)] + [prec(None, n=9)])
    assert few["insufficient"] and few["with_record"] == 4 and "buyer_wins" not in few
    many = outcome_shares(
        [
            prec("allowed", n=1),
            prec("allowed", n=2),
            prec("partly_allowed", n=3),
            prec("dismissed", n=4),
            prec("disposed_of", n=5),
            prec(None, n=6),
        ]
    )
    assert not many["insufficient"] and many["with_record"] == 5 and many["buyer_wins"] == 0.6
    assert many["interval_90"][0] < 0.6 < many["interval_90"][1]


def test_award_uses_median_precedent_rate_and_the_calculator():
    ci = CaseInput(
        "delayed_possession",
        CUTOFF,
        facts={"payment": ["2020-01-01;100000.00"], "possession_promised": ["2021-01-01"]},
    )
    a = award(
        ci, [prec("allowed", "9.30", 1), prec("allowed", "10.00", 2), prec("allowed", "10.85", 3)], CUTOFF
    )
    assert a["available"] and a["rate_pct"] == "10.000" and "median of 3" in a["rate_basis"]
    # 1 Jan 2021 -> 1 Jan 2025 = 1,461 days; 1,00,000 x 10% x 1461/365 = 40,027.40
    assert a["delay_interest"] == "40027.40"
    no_rate = award(ci, [prec("allowed", n=1)], CUTOFF)
    assert not no_rate["available"] and "interest rate" in no_rate["reason"]
    assert (
        award(CaseInput("refund", CUTOFF), [prec("allowed", "10", 1)], CUTOFF)["reason"]
        == "no verified payments"
    )


# ── Graph with a stand-in model and the test database ──

PRECEDENT_TEXT = [
    "The promoter failed to hand over possession by the due date. The plea of force majeure on account of "
    "NGT bans is rejected and the complainant is entitled to delay possession interest for every "
    "month of delay.",
    "The respondent pleaded force majeure because of the covid lockdown; the authority held the delay in "
    "possession is not covered and directed interest at the prescribed rate of 10.85% per annum.",
]


class StandIn:
    """Reads the precedent block from the prompt and answers with a mix of good and bad citations."""

    name = "stand-in"

    def __init__(self):
        self.prompts: list[str] = []

    @staticmethod
    def _first_excerpt(prompt: str):
        m = re.search(r"\[(P\d+)\][^\n]*\n  page (\d+): (.+)", prompt)
        return m.group(1), int(m.group(2)), m.group(3)[:90]

    def propose(self, prompt, schema):
        self.prompts.append(prompt)
        ref, page, quote = self._first_excerpt(prompt)
        good = agents.Cite(precedent=ref, page_no=page, quote=quote)
        if schema is agents.AdvocateOut and "advocate for the homebuyer" in prompt:
            return agents.AdvocateOut(
                arguments=[
                    agents.Argument(
                        heading="Possession is overdue", body="Delay interest is due.", citations=[good]
                    ),
                    agents.Argument(
                        heading="Invented precedent",
                        body="x",
                        citations=[
                            agents.Cite(
                                precedent=ref,
                                page_no=page,
                                quote="The authority awarded punitive damages of Rs 50 lakh",
                            )
                        ],
                    ),
                    agents.Argument(heading="Uncited point", body="y", citations=[]),
                ]
            )
        if schema is agents.AdvocateOut:
            return agents.AdvocateOut(
                arguments=[
                    agents.Argument(heading="Force majeure", body="Bans caused delay.", citations=[good]),
                    agents.Argument(
                        heading="Unknown precedent",
                        body="z",
                        citations=[agents.Cite(precedent="P99", page_no=1, quote=quote)],
                    ),
                ]
            )
        return agents.JudgeOut(
            outcome="allowed",
            reasoning="The force majeure plea fails on these precedents.",
            weak_points=[agents.WeakPoint(title="Late payment", detail="d", fix="f")],
            citations=[
                good,
                agents.Cite(precedent=ref, page_no=page, quote="a sentence that is not in the order at all"),
            ],
        )


@pytest.fixture
def world(db_engine):
    wipe = text("TRUNCATE orders, fetch_log, cases RESTART IDENTITY CASCADE")
    with db_engine.begin() as c:
        c.execute(wipe)
    with Session(db_engine) as s:
        for i in range(6):
            body = PRECEDENT_TEXT[i % 2]
            o = Order(
                source="hrera_gurugram",
                complaint_no=f"RERA-GRG-{i}-2023",
                case_type="HRERA Complaints",
                decided_on=date(2023, 1 + i, 1),
                pdf_url="u",
                pdf_sha256="e" * 64,
                page_count=1,
                text_source="text_layer",
                fetched_at=datetime.now(UTC),
            )
            o.pages.append(OrderPage(page_no=1, text=body, text_source="text_layer"))
            s.add(o)
            s.flush()
            s.add(OrderChunk(order_id=o.id, page_no=1, char_start=0, char_end=len(body), text=body))
            s.add(
                CaseRecord(
                    order_id=o.id,
                    claim_type="delayed_possession",
                    outcome=["allowed", "allowed", "partly_allowed", "dismissed", "allowed", "disposed_of"][
                        i
                    ],
                    interest_rate_pct=Decimal("10.85") if i < 3 else None,
                    extracted_by="test",
                )
            )
        case = Case(title="Demo", claim_type="delayed_possession", is_demo=True)
        doc = CaseDocument(filename="a.pdf", kind="agreement", sha256="f" * 64, page_count=1, storage_key="k")
        page = "Possession by 30th June 2021. Received Rs. 7,20,000/- dated 12.03.2018."
        doc.pages.append(CaseDocumentPage(page_no=1, text=page, text_source="text_layer"))
        case.documents.append(doc)
        s.add(case)
        s.flush()
        for key, value, quote in (
            ("possession_promised", "2021-06-30", "30th June 2021"),
            ("payment", "2018-03-12;720000.00", "Received Rs. 7,20,000/- dated 12.03.2018"),
        ):
            st = page.index(quote)
            s.add(
                Fact(
                    case_id=case.id,
                    document_id=doc.id,
                    key=key,
                    label=key,
                    value=value,
                    page_no=1,
                    char_start=st,
                    char_end=st + len(quote),
                    quote=quote,
                    confidence="high",
                )
            )
        real = Case(title="Real", claim_type="delayed_possession")
        s.add(real)
        s.commit()
        ids = {"demo": case.id, "real": real.id}
    yield db_engine, ids
    with db_engine.begin() as c:
        c.execute(wipe)


def test_gate_keeps_only_fully_verified_arguments_and_judge_sees_only_them(world):
    engine, ids = world
    llm = StandIn()
    with Session(engine) as s:
        run = run_case_hearing(s, ids["demo"], llm, embedder=None, cutoff=CUTOFF)
        s.commit()
        r = run.result
    assert run.status == "completed"
    args = r["arguments"]
    assert [a["heading"] for a in args["buyer"]] == ["Possession is overdue"]
    assert [a["heading"] for a in args["builder"]] == ["Force majeure"]
    removed = {a["heading"]: a["removed_because"] for a in args["removed"]}
    assert removed == {
        "Invented precedent": "a citation failed verification",
        "Uncited point": "no citation",
        "Unknown precedent": "a citation failed verification",
    }
    for a in args["buyer"] + args["builder"]:
        for c in a["citations"]:
            assert c["status"] == "verified" and c["stored_quote"]
    judge_prompt = llm.prompts[-1]
    assert "Possession is overdue" in judge_prompt and "Invented precedent" not in judge_prompt
    assert "Unknown precedent" not in judge_prompt
    assert r["judge"]["outcome"] == "allowed"
    assert len(r["judge"]["citations"]) == 1 and len(r["judge"]["citations_removed"]) == 1


def test_report_numbers_come_from_records_and_calculator(world):
    engine, ids = world
    with Session(engine) as s:
        r = run_case_hearing(s, ids["demo"], StandIn(), embedder=None, cutoff=CUTOFF).result
    shares = r["outcome_shares"]
    assert shares["with_record"] == 6 and shares["buyer_wins"] == round(4 / 6, 3)
    assert r["award"]["available"] and r["award"]["rate_pct"] == "10.850"
    assert all(p["decided_on"] < CUTOFF.isoformat() for p in r["precedents"])


def test_real_case_is_blocked_and_no_facts_is_refused(world):
    engine, ids = world
    llm = StandIn()
    with Session(engine) as s:
        with pytest.raises(PrivateDataBlocked):
            run_case_hearing(s, ids["real"], llm, embedder=None, cutoff=CUTOFF)
        s.execute(text("UPDATE cases SET is_demo = true WHERE id = :i"), {"i": ids["real"]})
        with pytest.raises(HearingNotPossible, match="No verified facts"):
            run_case_hearing(s, ids["real"], llm, embedder=None, cutoff=CUTOFF)
    assert llm.prompts == []


def test_no_precedent_before_cutoff_is_refused(world):
    engine, ids = world
    with Session(engine) as s, pytest.raises(HearingNotPossible, match="No similar orders"):
        run_case_hearing(s, ids["demo"], StandIn(), embedder=None, cutoff=date(2022, 1, 1))


def test_model_failure_is_stored_as_failed_run(world):
    engine, ids = world

    class Broken(StandIn):
        def propose(self, prompt, schema):
            raise RuntimeError("model unavailable")

    with Session(engine) as s:
        with pytest.raises(RuntimeError):
            run_case_hearing(s, ids["demo"], Broken(), embedder=None, cutoff=CUTOFF)
        s.commit()
        run = s.scalar(select(HearingRun))
    assert run.status == "failed" and "model unavailable" in run.error


def test_hearing_api_runs_and_returns_latest(world, monkeypatch):
    from app.hearing import jobs

    engine, ids = world
    monkeypatch.setattr(jobs, "get_engine", lambda: engine)  # the job opens its own session

    def session_override():
        with Session(engine) as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    owner = make_user(engine)
    with engine.begin() as c:
        c.execute(text("UPDATE cases SET user_id = :u"), {"u": owner.id})
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[current_user] = lambda: owner
    app.dependency_overrides[hearing_api.get_hearing_llm] = StandIn
    app.dependency_overrides[hearing_api.get_search_embedder] = lambda: None
    queued: list = []
    app.dependency_overrides[hearing_api.get_submit] = lambda: queued.append
    try:
        client = TestClient(app)
        demo = ids["demo"]
        assert client.get(f"/api/v1/cases/{demo}/hearing").status_code == 404
        res = client.post(f"/api/v1/cases/{demo}/hearing")
        assert res.status_code == 202, res.text
        run_id = res.json()["id"]
        assert res.json()["status"] == "running" and len(queued) == 1
        assert client.get(f"/api/v1/cases/{demo}/hearing/active").json()["id"] == run_id
        # A second start while one is running is refused, not duplicated.
        assert client.post(f"/api/v1/cases/{demo}/hearing").status_code == 409
        queued.pop()()  # the background job runs (here, on the test thread)
        done = client.get(f"/api/v1/cases/{demo}/hearing/runs/{run_id}").json()
        assert done["status"] == "completed" and done["result"]["judge"]["outcome"] == "allowed"
        assert client.get(f"/api/v1/cases/{demo}/hearing").json()["id"] == run_id
        assert client.get(f"/api/v1/cases/{demo}/hearing/active").json() is None
        assert client.post(f"/api/v1/cases/{ids['real']}/hearing").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_interrupted_runs_are_marked_failed(world, monkeypatch):
    from app.hearing import jobs

    engine, ids = world
    monkeypatch.setattr(jobs, "get_engine", lambda: engine)
    with Session(engine) as s:
        s.add(HearingRun(case_id=ids["demo"], cutoff=CUTOFF, models="m", status="running"))
        s.commit()
    assert jobs.fail_interrupted_runs() == 1
    with Session(engine) as s:
        run = s.scalar(select(HearingRun))
    assert run.status == "failed" and "restarted" in run.error and run.finished_at is not None


def test_a_hung_model_call_is_cut_off_by_the_hard_deadline():
    import time as _time

    from app.extraction.gemini import CallTimedOut, call_with_deadline

    started = _time.monotonic()
    with pytest.raises(CallTimedOut):
        call_with_deadline(lambda: _time.sleep(30), 0.5)
    assert _time.monotonic() - started < 5
    assert call_with_deadline(lambda: 42, 5) == 42
    with pytest.raises(ValueError):
        call_with_deadline(lambda: (_ for _ in ()).throw(ValueError("boom")), 5)


def test_no_transaction_stays_open_during_model_calls(world):
    engine, ids = world
    seen: list[bool] = []

    class Watching(StandIn):
        def __init__(self, session):
            super().__init__()
            self.session = session

        def propose(self, prompt, schema):
            seen.append(self.session.in_transaction())
            return super().propose(prompt, schema)

    with Session(engine) as s:
        run_case_hearing(s, ids["demo"], Watching(s), embedder=None, cutoff=CUTOFF)
    assert seen == [False, False, False]
