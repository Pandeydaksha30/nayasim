"""Run the four methods on the test set and collect predictions.

Methods 3 and 4 receive the same precedents for each case, so the only difference between them
is the debate (two advocates, citation gate, judge) versus a single model call.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.backtest.baselines import Buckets, Majority
from app.backtest.dataset import Example, case_input
from app.hearing.agents import LLM, RULES
from app.hearing.graph import run_graph
from app.hearing.inputs import ANSWER_LABELS, LABELS, build_precedents, precedent_block, summary_text
from app.retrieval.embedder import Embedder


class SingleOut(BaseModel):
    outcome: Literal["allowed", "partly_allowed", "dismissed", "disposed_of"]
    reasoning: str = Field(description="Two or three sentences.")


SINGLE = """You are the bench of a Real Estate Regulatory Authority in India. Predict the outcome on the
complainant's main relief from the case summary and the precedents below.
{rules}

CASE SUMMARY:
{summary}

PRECEDENTS (orders decided before {cutoff}):
{precedents}
"""


def legacy_summary_text(ci) -> str:
    """The case summary exactly as used in the 9 Nov 2026 backtest (before the "none verified"
    fix). Kept only as an experimental control: it lets a rerun show whether a change in results
    comes from the new wording or from the hosted model changing between runs."""
    from decimal import Decimal

    lines = [f"Claim: {ci.claim_type.replace('_', ' ')}. Hearing as of {ci.cutoff.isoformat()}."]
    for key, label in LABELS.items():
        if (v := ci.first(key)) is not None:
            lines.append(f"- {label}: {v}")
    pays = ci.payments
    if pays:
        total = sum((a for _, a in pays), Decimal(0))
        lines.append(f"- Payments by the buyer: {len(pays)}, total Rs {total}")
        lines += [f"    {d.isoformat()}: Rs {a}" for d, a in pays]
    else:
        lines.append("- Payments by the buyer: none verified")
    for qid, label in ANSWER_LABELS.items():
        if qid in ci.answers:
            lines.append(f"- {label} {ci.answers[qid]}")
    return "\n".join(lines)


@dataclass
class CaseResult:
    order_id: int
    complaint_no: str
    truth: str
    predictions: dict[str, str | None] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    precedents: int = 0
    gate: dict = field(default_factory=dict)  # citation counts from the debate
    seconds: float = 0.0


def _gate_counts(report: dict) -> dict:
    args = report["arguments"]
    kept = args["buyer"] + args["builder"]
    cites = [c for a in kept + args["removed"] for c in a["citations"]]
    judge = report["judge"]
    return {
        "arguments_kept": len(kept),
        "arguments_removed": len(args["removed"]),
        "citations": len(cites) + len(judge["citations"]) + len(judge["citations_removed"]),
        "citations_verified": sum(c["status"] == "verified" for c in cites) + len(judge["citations"]),
    }


def run_backtest(
    s: Session,
    train: list[Example],
    test: list[Example],
    cutoff: date,
    llm: LLM,
    embedder: Embedder | None,
    progress=print,
    methods: tuple[str, ...] = ("majority", "buckets", "single", "debate"),
    summary: str = "current",
) -> list[CaseResult]:
    summarise = legacy_summary_text if summary == "legacy" else summary_text
    majority, buckets = Majority(train), Buckets(train)
    results: list[CaseResult] = []
    for i, e in enumerate(test, 1):
        started = time.monotonic()
        r = CaseResult(e.order_id, e.complaint_no, e.outcome)
        r.predictions["majority"] = majority.predict(e)
        r.predictions["buckets"] = buckets.predict(e)
        ci = case_input(e, cutoff)
        precedents = build_precedents(s, ci, embedder)
        if not (s.new or s.dirty or s.deleted):
            s.commit()  # no transaction open during model calls
        r.precedents = len(precedents)
        if not precedents:
            r.errors["single"] = r.errors["debate"] = "no precedents before the cutoff"
        else:
            prompt = SINGLE.format(
                rules=RULES,
                summary=summarise(ci),
                precedents=precedent_block(precedents),
                cutoff=cutoff.isoformat(),
            )
            if "single" in methods:
                try:
                    r.predictions["single"] = llm.propose(prompt, SingleOut).outcome
                except Exception as ex:  # recorded per case, never dropped
                    r.errors["single"] = f"{type(ex).__name__}: {ex}"[:300]
            if "debate" in methods:
                try:
                    report = run_graph(s, llm, ci, precedents, as_of=cutoff)
                    r.predictions["debate"] = report["judge"]["outcome"]
                    r.gate = _gate_counts(report)
                except Exception as ex:
                    r.errors["debate"] = f"{type(ex).__name__}: {ex}"[:300]
        r.seconds = round(time.monotonic() - started, 1)
        results.append(r)
        preds = " ".join(f"{k}={v}" for k, v in r.predictions.items())
        progress(
            f"[{i}/{len(test)}] {e.complaint_no} truth={e.outcome} {preds}"
            + (f" errors={list(r.errors)}" if r.errors else "")
        )
    return results


def as_rows(results: list[CaseResult]) -> list[dict]:
    return [asdict(r) for r in results]
