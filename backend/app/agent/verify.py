"""Deterministic citation check for agent answers. Code, not a model.

D-labels are checked against the stored passage of the buyer's document (same check as the
document Q&A); O-labels are checked against the stored order page with the precedent verifier,
restricted to orders the run actually retrieved and decided before the cutoff.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.rag.answer import DocCite, check_citations
from app.verifier.citations import Citation, verify_citation

if TYPE_CHECKING:
    from app.agent.tools import ToolContext


def verify_cites(ctx: ToolContext, cites: list[dict]) -> tuple[list[dict], list[dict]]:
    good: list[dict] = []
    bad: list[dict] = []
    allowed = {h.order_id for h in ctx.order_evidence.values()}
    for c in cites:
        ref = str(c.get("ref", "")).strip().strip("[]").upper()
        quote = str(c.get("quote", ""))
        if ref in ctx.doc_evidence:
            p = ctx.doc_evidence[ref]
            g, b = check_citations([DocCite(ref="D1", quote=quote)], [p])
            if g:
                good.append({**g[0], "ref": ref, "source": "document"})
            else:
                bad.append({"ref": ref, "quote": quote, "reason": b[0]["reason"]})
        elif ref in ctx.order_evidence:
            h = ctx.order_evidence[ref]
            v = verify_citation(
                ctx.s,
                Citation(page_no=h.page_no, quote=quote, order_id=h.order_id),
                before=ctx.cutoff,
                allowed_orders=allowed,
            )
            if v.verified:
                good.append(
                    {
                        "ref": ref,
                        "source": "order",
                        "order_id": h.order_id,
                        "complaint_no": h.complaint_no,
                        "decided_on": h.decided_on.isoformat(),
                        "page_no": h.page_no,
                        "quote": v.stored_quote or quote,
                        "status": "verified",
                    }
                )
            else:
                bad.append({"ref": ref, "quote": quote, "reason": "; ".join(v.reasons)})
        elif ref in ctx.hearing_evidence:
            e = ctx.hearing_evidence[ref]
            v = verify_citation(
                ctx.s,
                Citation(page_no=e["page_no"], quote=quote, order_id=e["order_id"]),
                before=ctx.cutoff,
                allowed_orders={x["order_id"] for x in ctx.hearing_evidence.values()},
            )
            if v.verified:
                good.append(
                    {
                        "ref": ref,
                        "source": "order",
                        "order_id": e["order_id"],
                        "complaint_no": e["complaint_no"],
                        "decided_on": e["decided_on"],
                        "page_no": e["page_no"],
                        "quote": v.stored_quote or quote,
                        "status": "verified",
                    }
                )
            else:
                bad.append({"ref": ref, "quote": quote, "reason": "; ".join(v.reasons)})
        else:
            bad.append(
                {"ref": ref, "quote": quote, "reason": "names evidence that no tool returned in this run"}
            )
    return good, bad
