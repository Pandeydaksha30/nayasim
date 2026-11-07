"""The hearing as a LangGraph graph: buyer -> builder -> gate -> judge -> report.

The gate is the point of the design: each citation is mapped from its label ([P3]) to the
stored order and checked by app.verifier. An argument survives only if it cites at least one
precedent and every one of its citations is verified. The judge sees survivors only; the
judge's own citations are checked too, and failed ones are removed and recorded.
"""

from __future__ import annotations

from datetime import date
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.hearing import agents
from app.hearing.inputs import CaseInput, Precedent, precedent_block, summary_text
from app.hearing.stats import award, outcome_shares
from app.verifier.citations import Citation, verify_citation


class HearingState(TypedDict, total=False):
    buyer_raw: list[dict]
    builder_raw: list[dict]
    buyer: list[dict]
    builder: list[dict]
    removed: list[dict]
    judge: dict
    report: dict


def _check_cites(s: Session, cites: list[dict], precedents: list[Precedent], cutoff: date) -> list[dict]:
    by_ref = {p.ref: p for p in precedents}
    allowed = {p.order_id for p in precedents}
    out = []
    for c in cites:
        ref = str(c.get("precedent", "")).strip().strip("[]")
        p = by_ref.get(ref)
        if p is None:
            out.append({**c, "status": "rejected", "reasons": [f"unknown precedent label {ref!r}"]})
            continue
        v = verify_citation(
            s,
            Citation(page_no=c["page_no"], quote=c["quote"], order_id=p.order_id),
            before=cutoff,
            allowed_orders=allowed,
        )
        out.append(
            {
                "precedent": ref,
                "order_id": p.order_id,
                "complaint_no": p.complaint_no,
                "decided_on": p.decided_on.isoformat(),
                "page_no": c["page_no"],
                "quote": c["quote"],
                "status": v.status,
                "reasons": v.reasons,
                "stored_quote": v.stored_quote,
                "char_start": v.char_start,
                "char_end": v.char_end,
            }
        )
    return out


def _end_transaction(s: Session) -> None:
    """Close the read transaction before the next slow model call. A real run held one open for
    almost 2 hours while a call hung; long-open transactions block Postgres housekeeping."""
    if not (s.new or s.dirty or s.deleted):
        s.commit()


def build_graph(s: Session, llm: agents.LLM, ci: CaseInput, precedents: list[Precedent], as_of: date):
    summary = summary_text(ci)
    block = precedent_block(precedents)
    common = {"rules": agents.RULES, "summary": summary, "precedents": block, "cutoff": ci.cutoff.isoformat()}

    def buyer(_: HearingState) -> HearingState:
        out = llm.propose(agents.BUYER.format(**common), agents.AdvocateOut)
        return {"buyer_raw": [a.model_dump() for a in out.arguments[:3]]}

    def builder(_: HearingState) -> HearingState:
        out = llm.propose(agents.BUILDER.format(**common), agents.AdvocateOut)
        return {"builder_raw": [a.model_dump() for a in out.arguments[:3]]}

    def gate(state: HearingState) -> HearingState:
        kept: dict[str, list[dict]] = {"buyer": [], "builder": []}
        removed: list[dict] = []
        for side in ("buyer", "builder"):
            for a in state.get(f"{side}_raw", []):
                checked = _check_cites(s, a["citations"], precedents, ci.cutoff)
                arg = {**a, "side": side, "citations": checked}
                if checked and all(c["status"] == "verified" for c in checked):
                    kept[side].append(arg)
                else:
                    why = "no citation" if not checked else "a citation failed verification"
                    removed.append({**arg, "removed_because": why})
        _end_transaction(s)
        return {"buyer": kept["buyer"], "builder": kept["builder"], "removed": removed}

    def judge(state: HearingState) -> HearingState:
        prompt = agents.JUDGE.format(
            **common,
            buyer=agents.render_arguments(state["buyer"]),
            builder=agents.render_arguments(state["builder"]),
        )
        out = llm.propose(prompt, agents.JudgeOut)
        checked = _check_cites(s, [c.model_dump() for c in out.citations], precedents, ci.cutoff)
        _end_transaction(s)
        return {
            "judge": {
                "outcome": out.outcome,
                "reasoning": out.reasoning,
                "weak_points": [w.model_dump() for w in out.weak_points[:3]],
                "citations": [c for c in checked if c["status"] == "verified"],
                "citations_removed": [c for c in checked if c["status"] != "verified"],
            }
        }

    def report(state: HearingState) -> HearingState:
        return {
            "report": {
                "summary": summary,
                "precedents": [
                    {
                        "ref": p.ref,
                        "order_id": p.order_id,
                        "complaint_no": p.complaint_no,
                        "decided_on": p.decided_on.isoformat(),
                        "outcome": p.outcome,
                        "interest_rate_pct": str(p.interest_rate_pct)
                        if p.interest_rate_pct is not None
                        else None,
                        "pages": sorted({pg for pg, _ in p.excerpts}),
                    }
                    for p in precedents
                ],
                "outcome_shares": outcome_shares(precedents),
                "award": award(ci, precedents, as_of),
                "arguments": {
                    "buyer": state["buyer"],
                    "builder": state["builder"],
                    "removed": state["removed"],
                },
                "judge": state["judge"],
            }
        }

    g = StateGraph(HearingState)
    for name, fn in (
        ("buyer", buyer),
        ("builder", builder),
        ("gate", gate),
        ("judge", judge),
        ("report", report),
    ):
        g.add_node(name, fn)
    g.add_edge(START, "buyer")
    g.add_edge("buyer", "builder")
    g.add_edge("builder", "gate")
    g.add_edge("gate", "judge")
    g.add_edge("judge", "report")
    g.add_edge("report", END)
    return g.compile()


def run_graph(
    s: Session, llm: agents.LLM, ci: CaseInput, precedents: list[Precedent], as_of: date
) -> dict[str, Any]:
    return build_graph(s, llm, ci, precedents, as_of).invoke({})["report"]
