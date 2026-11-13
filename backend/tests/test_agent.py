"""Agent orchestration (app/agent): the model chooses tools, code runs them, limits hold,
citations are checked by code, runs are saved and only the case owner can see them.

The model is a scripted stand-in: each test states what the model "decides", so the loop's own
behaviour (not a model's) is what is tested.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent import jobs as agent_jobs
from app.agent.orchestrator import Final, FinalCite, Step, run_orchestrator
from app.agent.tools import ToolContext
from app.api import hearing as hearing_api
from app.api.hearing import get_hearing_llm
from app.auth.deps import current_user
from app.main import app
from app.retrieval.embedder import HashingEmbedder
from tests.conftest import make_user
from tests.test_buyer import api, upload  # noqa: F401  (api is a fixture)
from tests.test_case_rag import demo_case


class Script:
    """Returns the scripted decisions in order; records every prompt and schema it was sent."""

    name = "scripted"

    def __init__(self, *outs):
        self.outs = list(outs)
        self.calls: list[tuple[str, type]] = []

    def propose(self, prompt, schema):
        self.calls.append((prompt, schema))
        if not self.outs:
            raise AssertionError("the loop asked the model more often than scripted")
        out = self.outs.pop(0)
        if isinstance(out, Exception):
            raise out
        assert isinstance(out, schema), f"loop asked for {schema.__name__}, script has {type(out).__name__}"
        return out


def ctx_for(s: Session, case_id: str, llm) -> ToolContext:
    return ToolContext(
        s=s,
        case_id=uuid.UUID(case_id),
        claim_type="delay_possession",
        cutoff=date.today(),
        embedder=HashingEmbedder(),
        llm=llm,
    )


QUOTE = "hand over possession of the Apartment on or before 30th June 2021"


def test_model_chooses_tools_and_final_citations_are_checked(api, db_engine):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    llm = Script(
        Step(thought="Need the promised date", action="search_documents", query="possession date promised"),
        Step(thought="Enough", action="finish"),
        Final(
            answer="Possession was promised by 30 June 2021.",
            insufficient=False,
            citations=[
                FinalCite(ref="D1", quote=QUOTE),
                FinalCite(ref="D1", quote="possession on or before 30th June 2025"),  # altered year
                FinalCite(ref="O7", quote="anything"),  # never retrieved
            ],
        ),
    )
    steps: list[dict] = []
    with Session(db_engine) as s:
        out = run_orchestrator(ctx_for(s, case_id, llm), "When was possession promised?", steps.append)
    assert [st["action"] for st in steps] == ["search_documents"]
    assert steps[0]["ok"] and steps[0]["observation"]["passages"][0]["ref"] == "D1"
    assert out["stop_reason"] == "agent chose to finish" and out["grounded"]
    assert len(out["citations"]) == 1 and out["citations"][0]["page_no"] == 2
    reasons = {r["ref"]: r["reason"] for r in out["rejected_citations"]}
    assert "O7" in reasons and "no tool returned" in reasons["O7"] and len(out["rejected_citations"]) == 2
    # The model was asked for the next step (Step) twice, then for the answer (Final).
    assert [c[1] for c in llm.calls] == [Step, Step, Final]
    assert "OBJECTIVE:\nWhen was possession promised?" in llm.calls[0][0]


def test_step_limit_repeats_and_once_tools_are_enforced_by_code(api, db_engine):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    same = Step(thought="again", action="search_documents", query="possession")
    llm = Script(
        same,
        same,  # identical repeat: refused
        Step(thought="hearing", action="run_hearing"),  # no facts: tool error, not a crash
        Step(thought="interest", action="calculate_interest"),  # missing rate: tool error
        Step(thought="q", action="search_documents", query="price"),
        Step(thought="q", action="search_documents", query="parking"),
        Final(answer="x", insufficient=True),  # the 7th step is never asked for
    )
    steps: list[dict] = []
    with Session(db_engine) as s:
        out = run_orchestrator(ctx_for(s, case_id, llm), "Analyse this case fully please", steps.append)
    assert len(steps) == 6 and out["stop_reason"] == "step limit (6) reached"
    assert steps[1]["ok"] is False and "identical call" in steps[1]["observation"]["error"]
    assert steps[2]["ok"] is False and "No verified facts" in steps[2]["observation"]["error"]
    assert steps[3]["ok"] is False and "rate_pct" in steps[3]["observation"]["error"]
    assert out["insufficient"] and not out["grounded"]


def test_delegation_runs_a_specialist_loop_with_its_own_tools(api, db_engine):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    llm = Script(
        Step(thought="docs", action="delegate", agent="document_analysis", task="Find the possession clause"),
        # inside the specialist:
        Step(thought="not mine", action="search_orders", query="delay"),  # outside its tool set
        Step(thought="search", action="search_documents", query="possession clause"),
        Step(thought="done", action="finish"),
        Final(
            answer="Clause found on page 2.", insufficient=False, citations=[FinalCite(ref="D1", quote=QUOTE)]
        ),
        # back in the orchestrator:
        Step(thought="done", action="finish"),
        Final(
            answer="Possession was due 30 June 2021.",
            insufficient=False,
            citations=[FinalCite(ref="D1", quote=QUOTE)],
        ),
    )
    steps: list[dict] = []
    with Session(db_engine) as s:
        out = run_orchestrator(ctx_for(s, case_id, llm), "Check the possession clause", steps.append)
    assert [(st["agent"], st["action"], st["ok"]) for st in steps] == [
        ("document_analysis", "search_orders", False),
        ("document_analysis", "search_documents", True),
        ("orchestrator", "delegate", True),
    ]
    assert "not available to the document_analysis agent" in steps[0]["observation"]["error"]
    assert steps[2]["observation"]["verified_citations"][0]["ref"] == "D1"
    assert out["grounded"] and out["total_steps"] == 3


def test_two_model_failures_end_the_run_without_inventing_an_answer(api, db_engine):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    llm = Script(RuntimeError("503"), RuntimeError("503"))
    with Session(db_engine) as s:
        out = run_orchestrator(ctx_for(s, case_id, llm), "When was possession promised?")
    assert out["stop_reason"] == "model failed twice" and out["insufficient"] and out["citations"] == []


def test_interest_tool_uses_the_calculator_on_verified_facts(api, db_engine):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    with db_engine.begin() as c:
        doc = c.execute(text("SELECT id FROM case_documents WHERE case_id = :c"), {"c": case_id}).scalar()
        for key, value in (("payment", "2020-01-01;1000000"), ("possession_promised", "2021-06-30")):
            c.execute(
                text("""INSERT INTO facts (case_id, document_id, key, label, value, page_no, char_start,
                        char_end, quote, confidence) VALUES (:c, :d, :k, :k, :v, 1, 0, 5,
                        (SELECT substr(text, 1, 5) FROM case_document_pages
                         WHERE document_id = :d AND page_no = 1), 'high')"""),
                {"c": case_id, "d": doc, "k": key, "v": value},
            )
    llm = Script(
        Step(thought="money", action="calculate_interest", rate_pct=10.0),
        Step(thought="done", action="finish"),
        Final(answer="Interest computed.", insufficient=False),
    )
    steps: list[dict] = []
    with Session(db_engine) as s:
        run_orchestrator(ctx_for(s, case_id, llm), "How much interest is owed?", steps.append)
    obs = steps[0]["observation"]
    assert steps[0]["ok"] and obs["amount_paid"] == "1000000" and obs["possession_due"] == "2021-06-30"
    assert float(obs["refund_interest"]) > float(obs["delay_interest"]) > 0


@pytest.fixture
def run_now(db_engine, monkeypatch):
    monkeypatch.setattr(agent_jobs, "get_engine", lambda: db_engine)
    app.dependency_overrides[hearing_api.get_submit] = lambda: lambda fn: fn()
    yield


def test_api_runs_saves_and_protects_agent_runs(api, db_engine, run_now):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    app.dependency_overrides[get_hearing_llm] = lambda: Script(
        Step(thought="look", action="search_documents", query="possession date"),
        Step(thought="done", action="finish"),
        Final(answer="Due 30 June 2021.", insufficient=False, citations=[FinalCite(ref="D1", quote=QUOTE)]),
    )
    res = client.post(f"/api/v1/cases/{case_id}/agent", json={"objective": "When was possession due?"})
    assert res.status_code == 202, res.text
    run_id = res.json()["id"]
    got = client.get(f"/api/v1/cases/{case_id}/agent/runs/{run_id}").json()
    assert got["status"] == "completed" and got["steps"][0]["action"] == "search_documents"
    assert got["result"]["citations"][0]["status"] == "verified"
    assert [r["id"] for r in client.get(f"/api/v1/cases/{case_id}/agent/runs").json()] == [run_id]

    # Private case: never sent to the model.
    private = client.post("/api/v1/cases", json={"title": "Real"}).json()["id"]
    assert (
        client.post(f"/api/v1/cases/{private}/agent", json={"objective": "Analyse my case"}).status_code
        == 403
    )

    # Another user sees nothing.
    app.dependency_overrides[current_user] = lambda: make_user(db_engine, "other@example.com")
    assert client.get(f"/api/v1/cases/{case_id}/agent/runs/{run_id}").status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/agent/runs").status_code == 404
    assert (
        client.post(f"/api/v1/cases/{case_id}/agent", json={"objective": "Analyse this case"}).status_code
        == 404
    )


def test_interrupted_agent_runs_are_marked_failed(api, db_engine, run_now):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    with db_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO agent_runs (case_id, objective, model, status) VALUES (:c, 'x', 'm', 'running')"
            ),
            {"c": case_id},
        )
    assert agent_jobs.fail_interrupted_agent_runs() == 1


def test_fact_citations_are_checked_against_the_facts_page(api, db_engine):  # noqa: F811
    client, _, _ = api
    case_id = demo_case(client)
    with db_engine.begin() as c:
        doc = c.execute(
            text(
                "SELECT document_id FROM case_document_pages p JOIN case_documents d ON d.id = p.document_id "
                "WHERE d.case_id = :c AND p.page_no = 2"
            ),
            {"c": case_id},
        ).scalar()
        page = c.execute(
            text("SELECT text FROM case_document_pages WHERE document_id = :d AND page_no = 2"), {"d": doc}
        ).scalar()
        start = page.index("30th June 2021")
        c.execute(
            text("""INSERT INTO facts (case_id, document_id, key, label, value, page_no, char_start,
                    char_end, quote, confidence) VALUES (:c, :d, 'possession_promised',
                    'Possession promised by',
                    '2021-06-30', 2, :s, :e, '30th June 2021', 'high')"""),
            {"c": case_id, "d": doc, "s": start, "e": start + len("30th June 2021")},
        )
    llm = Script(
        Step(thought="facts", action="get_facts"),
        Step(thought="done", action="finish"),
        Final(
            answer="Possession was due on 30 June 2021.",
            insufficient=False,
            citations=[
                FinalCite(ref="F1", quote="on or before 30th June 2021"),
                FinalCite(ref="F1", quote="on or before 30th June 2022"),  # altered year
            ],
        ),
    )
    steps: list[dict] = []
    with Session(db_engine) as s:
        out = run_orchestrator(ctx_for(s, case_id, llm), "When was possession due?", steps.append)
    assert steps[0]["observation"]["facts"][0]["ref"] == "F1"
    assert [c["page_no"] for c in out["citations"]] == [2] and len(out["rejected_citations"]) == 1


def test_time_limit_and_model_timeouts_stop_the_run(api, db_engine):  # noqa: F811
    from app.extraction.gemini import CallTimedOut

    client, _, _ = api
    case_id = demo_case(client)
    llm = Script()  # never called: the budget is already spent
    with Session(db_engine) as s:
        out = run_orchestrator(ctx_for(s, case_id, llm), "When was possession due?", time_budget_s=0)
    assert out["stop_reason"] == "time limit reached" and out["insufficient"] and llm.calls == []
    llm = Script(CallTimedOut("no answer within 150 s"), CallTimedOut("no answer within 150 s"))
    steps: list[dict] = []
    with Session(db_engine) as s:
        out = run_orchestrator(ctx_for(s, case_id, llm), "When was possession due?", steps.append)
    assert out["stop_reason"] == "model failed twice"
    assert [st["action"] for st in steps] == ["model_error", "model_error"]
    assert "CallTimedOut" in steps[0]["observation"]["error"]
