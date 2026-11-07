"""Step 9: backtest data split, leak checks, baselines, metrics, runner."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.backtest.baselines import Buckets, Majority, delay_band
from app.backtest.dataset import Example, case_input, load
from app.backtest.metrics import accuracy, confusion, macro_f1, mcnemar_exact, score
from app.backtest.run import SingleOut, run_backtest
from app.db.models import CaseRecord, Order, OrderChunk, OrderPage
from app.hearing.inputs import summary_text
from tests.test_hearing import StandIn

CUTOFF = date(2025, 1, 1)


def ex(outcome, claim="delayed_possession", due=date(2020, 1, 1), decided=date(2025, 6, 1), i=1):
    return Example(i, f"C{i}", decided, claim, due, Decimal("1000000"), outcome)


# ── Metrics ──


def test_accuracy_and_macro_f1_match_hand_values():
    truth = ["allowed", "allowed", "partly_allowed", "dismissed"]
    pred = ["allowed", "partly_allowed", "partly_allowed", "disposed_of"]
    assert accuracy(truth, pred) == 0.5
    # allowed: P=1, R=.5 -> .667; partly: P=.5, R=1 -> .667; dismissed: 0 -> mean .444
    assert round(macro_f1(truth, pred), 3) == 0.444
    table = confusion(truth, pred)
    assert table["dismissed"]["disposed_of"] == 1 and table["allowed"]["partly_allowed"] == 1


def test_mcnemar_exact():
    assert abs(mcnemar_exact(0, 6) - 2 / 64) < 1e-9  # 6 discordant pairs all one way
    assert mcnemar_exact(3, 3) == 1.0
    assert mcnemar_exact(0, 0) == 1.0


def test_score_uses_only_cases_every_method_answered():
    rows = [
        {
            "truth": "allowed",
            "predictions": {
                "majority": "allowed",
                "buckets": "allowed",
                "single": "allowed",
                "debate": "dismissed",
            },
            "errors": {},
            "gate": {},
        },
        {
            "truth": "dismissed",
            "predictions": {"majority": "allowed", "buckets": "allowed"},
            "errors": {"single": "x", "debate": "x"},
            "gate": {},
        },
    ]
    sc = score(rows)
    assert sc["cases"] == 2 and sc["scored"] == 1 and sc["errors"]["single"] == 1
    assert sc["methods"]["single"]["accuracy"] == 1.0 and sc["methods"]["debate"]["accuracy"] == 0.0
    assert sc["debate_vs_single"]["only_single_right"] == 1


# ── Baselines ──


def test_majority_and_bucket_fallbacks():
    train = (
        [ex("partly_allowed", i=i) for i in range(4)]
        + [ex("allowed", claim="refund", i=10 + i) for i in range(3)]
        + [ex("dismissed", due=None, i=20 + i) for i in range(2)]
    )
    assert Majority(train).predict(ex("allowed")) == "partly_allowed"
    b = Buckets(train)
    assert b.predict(ex("x", claim="refund")) == "allowed"  # refund bucket has 3
    assert b.predict(ex("x", due=None)) == "partly_allowed"  # unknown bucket has 2 -> claim type
    assert b.predict(ex("x", claim="other")) == "partly_allowed"  # unseen claim -> overall
    assert delay_band(ex("x", due=date(2024, 1, 1))) == "<2y" and delay_band(ex("x", due=None)) == "unknown"


# ── Data and leak checks against the database ──

ORDER_TEXT = (
    "The promoter failed to hand over possession by the due date and the plea of force majeure is "
    "rejected; delay possession interest for every month of delay is allowed."
)


@pytest.fixture
def records(db_engine):
    wipe = text("TRUNCATE orders, fetch_log, cases RESTART IDENTITY CASCADE")
    with db_engine.begin() as c:
        c.execute(wipe)
    plan = [
        (
            date(2023, 1 + i, 1),
            ["allowed", "partly_allowed", "dismissed", "allowed", "allowed", "disposed_of"][i],
        )
        for i in range(6)
    ] + [(date(2025, 3, 1), "allowed"), (date(2025, 4, 1), "dismissed"), (date(2025, 5, 1), "withdrawn")]
    with Session(db_engine) as s:
        for i, (decided, outcome) in enumerate(plan):
            o = Order(
                source="hrera_gurugram",
                complaint_no=f"RERA-GRG-{i}-X",
                case_type="HRERA Complaints",
                decided_on=decided,
                pdf_url="u",
                pdf_sha256="a" * 64,
                page_count=1,
                text_source="text_layer",
                fetched_at=datetime.now(UTC),
            )
            o.pages.append(OrderPage(page_no=1, text=ORDER_TEXT, text_source="text_layer"))
            s.add(o)
            s.flush()
            s.add(
                OrderChunk(order_id=o.id, page_no=1, char_start=0, char_end=len(ORDER_TEXT), text=ORDER_TEXT)
            )
            s.add(
                CaseRecord(
                    order_id=o.id,
                    claim_type="delayed_possession",
                    outcome=outcome,
                    possession_due=date(2019, 12, 31),
                    amount_paid=Decimal("2500000"),
                    interest_rate_pct=Decimal("10.85"),
                    extracted_by="test",
                )
            )
        s.commit()
    yield db_engine
    with db_engine.begin() as c:
        c.execute(wipe)


def test_split_respects_cutoff_and_merits_outcomes(records):
    with Session(records) as s:
        train, test = load(s, CUTOFF, split="train"), load(s, CUTOFF, split="test")
    assert all(e.decided_on < CUTOFF for e in train) and len(train) == 5  # disposed_of excluded
    assert all(e.decided_on >= CUTOFF for e in test) and [e.outcome for e in test] == ["allowed", "dismissed"]


def test_test_case_input_carries_no_outcome_or_order_text(records):
    with Session(records) as s:
        e = load(s, CUTOFF, split="test")[1]
    ci = case_input(e, CUTOFF)
    summary = summary_text(ci).lower()
    assert "dismiss" not in summary and "allowed" not in summary and "force majeure" not in summary
    assert ci.cutoff == CUTOFF and ci.facts["possession_promised"] == ["2019-12-31"]


def test_runner_predicts_with_precedents_only_from_before_the_cutoff(records):
    class Counting(StandIn):
        def propose(self, prompt, schema):
            if schema is SingleOut:
                self.prompts.append(prompt)
                return SingleOut(outcome="allowed", reasoning="r")
            return super().propose(prompt, schema)

    llm = Counting()
    with Session(records) as s:
        train, test = load(s, CUTOFF, split="train"), load(s, CUTOFF, split="test")
        results = run_backtest(s, train, test, CUTOFF, llm, embedder=None, progress=lambda _: None)
    assert [r.truth for r in results] == ["allowed", "dismissed"]
    for r in results:
        assert set(r.predictions) == {"majority", "buckets", "single", "debate"} and not r.errors
        assert r.precedents == 6  # the 2023 orders only
        assert r.gate["citations_verified"] >= 1
    for p in llm.prompts:
        assert "decided 2025" not in p  # no precedent decided in the test year
        assert "decided 2023" in p


def test_model_error_is_recorded_not_guessed(records):
    class Failing(StandIn):
        def propose(self, prompt, schema):
            raise RuntimeError("quota")

    with Session(records) as s:
        train, test = load(s, CUTOFF, split="train"), load(s, CUTOFF, split="test")
        results = run_backtest(s, train, test, CUTOFF, Failing(), embedder=None, progress=lambda _: None)
    for r in results:
        assert "single" not in r.predictions and "debate" not in r.predictions
        assert "quota" in r.errors["single"] and "quota" in r.errors["debate"]
