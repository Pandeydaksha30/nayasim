"""The three hearing roles: prompts and output schemas.

The advocates may cite only the numbered precedents they are shown ([P1], [P2], ...), with a
page and a verbatim quote; code checks every citation (app.verifier). The judge sees only the
arguments that survived that check. None of them computes money.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field


class Cite(BaseModel):
    precedent: str = Field(description='Precedent label, e.g. "P3".')
    page_no: int
    quote: str = Field(description="Words copied exactly from that page excerpt, at least one full clause.")


class Argument(BaseModel):
    heading: str = Field(description="One-line point.")
    body: str = Field(description="Two to four sentences.")
    citations: list[Cite] = Field(default_factory=list)


class AdvocateOut(BaseModel):
    arguments: list[Argument] = Field(default_factory=list, description="Up to 3 arguments.")


class WeakPoint(BaseModel):
    title: str
    detail: str
    fix: str = Field(description="What the buyer can do about it.")


class JudgeOut(BaseModel):
    outcome: Literal["allowed", "partly_allowed", "dismissed", "disposed_of"]
    reasoning: str = Field(description="Reasoned view in 4-8 sentences, relying only on the arguments shown.")
    weak_points: list[WeakPoint] = Field(
        default_factory=list, description="Up to 3 weaknesses in the buyer's case."
    )
    citations: list[Cite] = Field(default_factory=list)


class LLM(Protocol):
    name: str

    def propose(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...


RULES = """Rules:
- Use ONLY the case summary and the precedent excerpts below. Do not rely on any other case or law
  you remember; if a point has no support in the excerpts, do not make it.
- Every argument must cite at least one precedent by its label ([P1], [P2], ...), with the page
  number and a quote copied EXACTLY from that page excerpt (no paraphrase, no "...").
- Do not calculate any amounts of money.
- Plain English, no flattery, no certainty you do not have."""

BUYER = """You are the advocate for the homebuyer (complainant) before a Real Estate Regulatory Authority in India.
Make up to 3 of the strongest arguments for the buyer's relief.
{rules}

CASE SUMMARY (verified from the buyer's documents and answers):
{summary}

PRECEDENTS (orders decided before {cutoff}):
{precedents}
"""

BUILDER = """You are the advocate for the builder (respondent) before a Real Estate Regulatory Authority in India.
Make up to 3 defences a builder would realistically raise against this complaint, the way builders
argued in the precedents.
{rules}

CASE SUMMARY:
{summary}

PRECEDENTS (orders decided before {cutoff}):
{precedents}
"""

JUDGE = """You are the bench of a Real Estate Regulatory Authority in India. Weigh the arguments below.
They are the only arguments before you; arguments whose citations failed verification were removed.
Decide the likely outcome on the buyer's main relief, give your reasons, and list up to 3 weak points
in the buyer's case with what the buyer can do about each.
{rules}

CASE SUMMARY:
{summary}

BUYER'S ARGUMENTS:
{buyer}

BUILDER'S ARGUMENTS:
{builder}

PRECEDENTS (orders decided before {cutoff}):
{precedents}
"""


def render_arguments(args: list[dict]) -> str:
    if not args:
        return "(none survived verification)"
    lines = []
    for i, a in enumerate(args, 1):
        cites = "; ".join(f"[{c['precedent']}] p.{c['page_no']}" for c in a["citations"])
        lines.append(f"{i}. {a['heading']} — {a['body']} (cites {cites})")
    return "\n".join(lines)
