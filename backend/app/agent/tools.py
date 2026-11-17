"""The tools an agent may call. All read the database; only run_hearing writes (it saves the
hearing it ran, like the hearing page does).

Every tool takes the run's ToolContext and returns an observation: a short, JSON-safe dict the
model sees on its next decision. Passages and precedent excerpts are registered as evidence under
labels (D1, D2... for the case's documents, O1, O2... for public orders); the final answer may
cite only those labels, and every such citation is checked by code (app/agent/verify.py).

A tool that fails raises ToolError (or any exception); the loop turns it into an observation.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.buyer.facts import USABLE
from app.calculator.interest import (
    CalculationError,
    Payment,
    delay_end,
    delay_interest,
    refund_with_interest,
)
from app.db.models import Fact
from app.hearing.agents import LLM
from app.retrieval.case_search import Passage, search_case
from app.retrieval.embedder import Embedder
from app.retrieval.search import Hit, search

SNIPPET = 600  # characters of each passage shown to the model


class ToolError(ValueError):
    """A tool could not run with these arguments; the message is shown to the model."""


@dataclass
class ToolContext:
    s: Session
    case_id: uuid.UUID
    claim_type: str
    cutoff: date
    embedder: Embedder | None
    llm: LLM
    doc_evidence: dict[str, Passage] = field(default_factory=dict)
    order_evidence: dict[str, Hit] = field(default_factory=dict)
    hearing: dict | None = None
    hearing_run_id: int | None = None
    hearing_evidence: dict[str, dict] = field(default_factory=dict)  # H1, H2...: verified hearing citations
    fact_evidence: dict[str, Passage] = field(default_factory=dict)  # F1, F2...: the page a fact came from

    def add_doc(self, p: Passage) -> str:
        for ref, q in self.doc_evidence.items():
            if q.chunk_id == p.chunk_id:
                return ref
        ref = f"D{len(self.doc_evidence) + 1}"
        self.doc_evidence[ref] = p
        return ref

    def add_order(self, h: Hit) -> str:
        for ref, q in self.order_evidence.items():
            if q.chunk_id == h.chunk_id:
                return ref
        ref = f"O{len(self.order_evidence) + 1}"
        self.order_evidence[ref] = h
        return ref


def _need(args: dict, key: str) -> str:
    v = (args.get(key) or "").strip() if isinstance(args.get(key), str) else args.get(key)
    if not v:
        raise ToolError(f"argument '{key}' is required")
    return v


def search_documents(ctx: ToolContext, args: dict) -> dict:
    query = _need(args, "query")
    hits, mode = search_case(ctx.s, ctx.case_id, query, ctx.embedder, k=5)
    return {
        "source": "the buyer's uploaded documents",
        "mode": mode,
        "passages": [
            {"ref": ctx.add_doc(h), "file": h.filename, "page": h.page_no, "text": h.text[:SNIPPET]}
            for h in hits
        ],
    }


def get_facts(ctx: ToolContext, args: dict) -> dict:
    from app.db.models import CaseDocument, CaseDocumentPage

    rows = ctx.s.scalars(select(Fact).where(Fact.case_id == ctx.case_id, USABLE).order_by(Fact.id)).all()
    out = []
    for f in rows:
        ref = next((r for r, p in ctx.fact_evidence.items() if p.chunk_id == -f.id), None)
        if ref is None:
            page = ctx.s.get(CaseDocumentPage, (f.document_id, f.page_no))
            doc = ctx.s.get(CaseDocument, f.document_id)
            ref = f"F{len(ctx.fact_evidence) + 1}"
            # The fact's whole page is the evidence: a quote cited as F<n> must be found on it.
            ctx.fact_evidence[ref] = Passage(
                -f.id,
                f.document_id,
                doc.filename,
                doc.kind,
                f.page_no,
                0,
                len(page.text or ""),
                page.text or "",
                1.0,
            )
        out.append(
            {
                "ref": ref,
                "key": f.key,
                "label": f.label,
                "value": f.value,
                "file": ctx.fact_evidence[ref].filename,
                "page": f.page_no,
                "quote": f.quote[:300],
                "confirmed": f.confirmed,
            }
        )
    return {
        "claim_type": ctx.claim_type,
        "facts": out,
        "note": "Facts were extracted from the documents and checked against the page text by code. "
        "Cite a fact by its ref (F1...) with words from its quote."
        if rows
        else "No facts have been extracted for this case yet.",
    }


def search_orders(ctx: ToolContext, args: dict) -> dict:
    query = _need(args, "query")
    res = search(ctx.s, query, before=ctx.cutoff, embedder=ctx.embedder, k=5)
    return {
        "source": f"public HRERA Gurugram orders decided before {ctx.cutoff.isoformat()}",
        "mode": res.mode,
        "excerpts": [
            {
                "ref": ctx.add_order(h),
                "complaint_no": h.complaint_no,
                "decided_on": h.decided_on.isoformat(),
                "page": h.page_no,
                "text": h.text[:SNIPPET],
            }
            for h in res.hits
        ],
    }


def verify_quote(ctx: ToolContext, args: dict) -> dict:
    from app.agent.verify import verify_cites

    ref, quote = _need(args, "ref"), _need(args, "quote")
    good, bad = verify_cites(ctx, [{"ref": ref, "quote": quote}])
    if good:
        return {"verified": True, "stored_quote": good[0]["quote"], "page": good[0]["page_no"]}
    return {"verified": False, "reason": bad[0]["reason"]}


def _offer_date(ctx: ToolContext) -> date | None:
    for f in ctx.s.scalars(
        select(Fact).where(Fact.case_id == ctx.case_id, USABLE, Fact.key == "offer_of_possession_date")
    ):
        try:
            return date.fromisoformat(f.value)
        except ValueError:
            continue
    return None


def _payments_and_due(ctx: ToolContext) -> tuple[list[Payment], date | None]:
    pays: list[Payment] = []
    due: date | None = None
    for f in ctx.s.scalars(select(Fact).where(Fact.case_id == ctx.case_id, USABLE).order_by(Fact.id)):
        if f.key == "payment":
            try:
                d, a = f.value.split(";")
                pays.append(Payment(date.fromisoformat(d), Decimal(a)))
            except (ValueError, InvalidOperation):
                continue
        elif f.key == "possession_promised" and due is None:
            try:
                due = date.fromisoformat(f.value)
            except ValueError:
                pass
    return pays, due


def calculate_interest(ctx: ToolContext, args: dict) -> dict:
    rate = args.get("rate_pct")
    if rate is None:
        raise ToolError("argument 'rate_pct' (annual interest rate, e.g. 10.80) is required")
    try:
        rate_d = Decimal(str(rate))
    except InvalidOperation as e:
        raise ToolError("rate_pct must be a number") from e
    pays, due = _payments_and_due(ctx)
    if not pays:
        raise ToolError("no verified payments in the case facts; interest cannot be calculated")
    as_of = ctx.cutoff
    until, until_basis = delay_end(as_of, _offer_date(ctx))
    try:
        refund = refund_with_interest(pays, as_of, rate_d)
        delay = delay_interest(pays, due, until, rate_d) if due else None
    except CalculationError as e:
        raise ToolError(str(e)) from e
    return {
        "method": "simple interest, computed by code (app/calculator/interest.py)",
        "rate_pct": str(rate_d),
        "as_of": as_of.isoformat(),
        "amount_paid": str(sum(p.amount for p in pays)),
        # Interest only, never principal + interest: the names say exactly what each figure is.
        "delay_interest": str(delay.interest) if delay else None,
        "refund_interest": str(refund.interest),
        "refund_total_with_interest": str(refund.total),
        "possession_due": due.isoformat() if due else None,
        "delay_interest_until": until.isoformat(),
        "delay_interest_until_basis": until_basis,
    }


def estimate_outcome(ctx: ToolContext, args: dict) -> dict:
    from app.insights.estimate import outcome_estimate

    _, due = _payments_and_due(ctx)
    return outcome_estimate(ctx.s, ctx.claim_type, due, ctx.cutoff)


def run_hearing(ctx: ToolContext, args: dict) -> dict:
    """The existing hearing simulation (buyer advocate, builder advocate, citation gate, judge).

    Saved as a hearing run of the case, so it also appears on the hearing page."""
    from datetime import UTC, datetime

    from app.db.models import HearingRun
    from app.hearing.graph import run_graph
    from app.hearing.runner import HearingNotPossible, prepare_case_hearing

    if ctx.hearing is not None:
        raise ToolError("the hearing has already been run in this analysis; use its result")
    try:
        prep = prepare_case_hearing(ctx.s, ctx.case_id, ctx.embedder, ctx.cutoff)
    except HearingNotPossible as e:
        raise ToolError(str(e)) from e
    report = run_graph(ctx.s, ctx.llm, prep.case_input, prep.precedents, as_of=prep.cutoff)
    run = HearingRun(
        case_id=ctx.case_id,
        cutoff=prep.cutoff,
        models=ctx.llm.name,
        status="completed",
        result=report,
        finished_at=datetime.now(UTC),
    )
    ctx.s.add(run)
    ctx.s.flush()
    ctx.hearing, ctx.hearing_run_id = report, run.id
    j = report["judge"]
    args_ = report["arguments"]
    return {
        "hearing_run_id": run.id,
        "judge_outcome": j["outcome"],
        "judge_reasoning": j["reasoning"][:1200],
        "weak_points": [w["title"] for w in j["weak_points"]],
        "verified_judge_citations": len(j["citations"]),
        "buyer_arguments_kept": len(args_["buyer"]),
        "builder_arguments_kept": len(args_["builder"]),
        "arguments_removed_by_citation_check": len(args_["removed"]),
        "precedent_outcome_shares": report["outcome_shares"],
        "verified_citations": _register_hearing_cites(ctx, report),
    }


def _register_hearing_cites(ctx: ToolContext, report: dict) -> list[dict]:
    """The citations that passed the hearing's code check become evidence H1, H2... the answer may cite."""
    cites = [c for a in report["arguments"]["buyer"] + report["arguments"]["builder"] for c in a["citations"]]
    cites += report["judge"]["citations"]
    out = []
    for c in cites:
        if c.get("status") != "verified" or not c.get("stored_quote"):
            continue
        if any(
            e["order_id"] == c["order_id"] and e["quote"] == c["stored_quote"]
            for e in ctx.hearing_evidence.values()
        ):
            continue
        ref = f"H{len(ctx.hearing_evidence) + 1}"
        ctx.hearing_evidence[ref] = {
            "order_id": c["order_id"],
            "complaint_no": c["complaint_no"],
            "decided_on": c["decided_on"],
            "page_no": c["page_no"],
            "quote": c["stored_quote"],
        }
        out.append(
            {
                "ref": ref,
                "complaint_no": c["complaint_no"],
                "page": c["page_no"],
                "quote": c["stored_quote"][:300],
            }
        )
    return out[:12]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: str  # how to fill the step's argument fields
    fn: Callable[[ToolContext, dict], dict]
    once: bool = False


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in (
        Tool(
            "search_documents",
            "Find passages in the buyer's own uploaded documents.",
            "query",
            search_documents,
        ),
        Tool(
            "get_facts",
            "List the facts already extracted and verified from the documents.",
            "none",
            get_facts,
        ),
        Tool(
            "search_orders",
            "Find excerpts of past HRERA Gurugram orders (precedents) decided before today.",
            "query",
            search_orders,
        ),
        Tool(
            "verify_quote",
            "Check by code whether a quote really appears in a passage or excerpt you have seen.",
            "ref (e.g. D2 or O3), quote",
            verify_quote,
        ),
        Tool(
            "calculate_interest",
            "Compute refund interest and delay interest from the verified payments, by code. Use only a rate "
            "stated in the objective or task; never choose a rate yourself; if none is given, skip it.",
            "rate_pct",
            calculate_interest,
        ),
        Tool(
            "estimate_outcome",
            "How past orders with the same claim type and delay ended (rule-based, 72.9% on test).",
            "none",
            estimate_outcome,
        ),
        Tool(
            "run_hearing",
            "Run the full simulated hearing (two advocates, citation check, judge). Slow: several model "
            "calls. Use at most once, only when the objective needs a hearing or judge assessment.",
            "none",
            run_hearing,
            once=True,
        ),
    )
}


def describe(names: list[str]) -> str:
    return "\n".join(
        f"- {TOOLS[n].name}({TOOLS[n].args}): {TOOLS[n].description}" for n in names if n in TOOLS
    )


def jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [jsonable(v) for v in x]
    if isinstance(x, date | Decimal | uuid.UUID):
        return str(x)
    return x
