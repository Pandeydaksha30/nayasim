"""Leakage-free case input from an order: the part written before the authority's own reasoning.

A full HRERA Gurugram order sets out, in this order: the unit and project details, the facts of
the complaint, the relief sought, the respondent's reply — and then the authority's part. Everything
before the authority's part is what the parties filed: roughly what a buyer's own papers plus the
builder's reply would show, without the decision.

Where the authority's part starts is the EARLIEST of (conservative: losing some of the reply is
acceptable, leaking the decision is not):
1. a section heading at the start of a line ("E. Jurisdiction of the authority", "Findings on ...",
   "Observations of the authority", "Directions of the authority", ...);
2. the same headings in the middle of a line (older orders run them into the text:
   "Findings and directions of the authority 22. Jurisdiction of the authority- ...");
3. the authority's own voice: "the authority observes", "the authority is of the view",
   "the authority has complete / territorial jurisdiction", "the authority holds / finds that",
   and the standard "leaving aside compensation which is to be decided by the adjudicating officer".

Measured on 135 merits orders whose first heading was found (10 Nov 2026): 42 had the authority's
voice BEFORE that heading — some of it the decision itself ("the authority is of the view that
complainant cannot be refunded the amount") — because OCR had damaged the heading. Rule 3 exists
for those.

Safeguards that make an order unusable rather than risk a leak:
- no start of the authority's part found (e.g. short "proceedings of the day" orders) -> None;
- what remains is too short to be a statement of facts -> None;
- decision wording ("complaint is allowed", "respondent is directed to", ...) still present -> None.

Known, accepted residue: the unit-details table at the top is compiled by the authority's office
and may state a due date of possession; it records the agreement's terms, not a finding on them.
Hand check of split points: `python -m scripts.benchmark facts-export` (docs/annotation-guide.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# OCR in these orders often reads j as i ("iurisdiction") and drops spaces ("ofthe").
_SP = r"\s*"
_J = r"[jifl|]"  # OCR reads the j of "jurisdiction" as i, f, l or |
_HEADS = (
    rf"{_J}urisdiction{_SP}of{_SP}the{_SP}au"
    rf"|territorial{_SP}{_J}urisdiction"
    rf"|subject{_SP}-?{_SP}matter{_SP}{_J}urisdiction"
    rf"|findings{_SP}(?:on|of|regarding|and{_SP}directions)"
    rf"|observations?{_SP}(?:of|by){_SP}the{_SP}authority"
    rf"|directions{_SP}(?:of|issued{_SP}by){_SP}the{_SP}authority"
    rf"|issues?{_SP}(?:for|before){_SP}(?:consideration|determination|the{_SP}authority)"
)
HEADING_LINE = re.compile(
    r"(?im)^[ \t]*(?:[A-K][ \t]*[.)][ \t]*)?(?:[ivx]+[ \t]*[.)][ \t]*)?(?P<head>" + _HEADS + ")"
)
HEADING_INLINE = re.compile(r"(?i)(?P<head>" + _HEADS + ")")
# The authority speaking about itself. Deliberately broad: a builder's reply arguing "the authority
# has no jurisdiction" is cut too, which loses some reply text but never lets a finding through.
AUTHORITY_VOICE = re.compile(
    r"(?i)(?P<head>\bthe\s*authority\s+(?:"
    r"observe[sd]?|is\s+o[fl]\s+the\s+(?:considered\s+)?(?:view|opinion)"
    r"|has\s+(?:complete|territorial|decided|no\s+(?:option|jurisdiction))"
    r"|holds\b|finds\s+that|is\s+satisfied|is\s+proceeding|is\s+empowered|deems\b"
    r")"
    r"|leaving\s+aside\s+compensation\s+which\s+is\s+to\s+be\s+decided"
    r"|\bon\s+consideration\s+of\s+the\s+(?:circumstances|facts|documents)"
    r"|\barguments\s+(?:have\s+been\s+)?heard"
    r")"
)

# Wording that only the authority's decision contains. Still present after the cut = unsafe.
DECISION = re.compile(
    r"(?i)\b(?:complaint|application|matter)\s+(?:is|stands|be|is\s+hereby)\s+"
    r"(?:allowed|dismissed|disposed|rejected|partly\s+allowed)"
    r"|\b(?:respondent|promoter)\s+is\s+(?:hereby\s+)?directed\s+to"
    r"|\bthe\s+authority\s+(?:hereby\s+)?(?:directs|orders)\b"
    r"|\bhereby\s+(?:direct|order)s?\b"
)

MIN_CHARS = 1500
# Prompt budget. When the parties' part is longer, its start (unit and project details) and its
# end (relief sought and the respondent's reply, which come just before the cut) are kept and the
# middle of the narrative is dropped.
HEAD_CHARS, TAIL_CHARS = 5000, 13000
MAX_CHARS = HEAD_CHARS + TAIL_CHARS


@dataclass(frozen=True)
class FactsSplit:
    text: str  # the parties' part, up to MAX_CHARS
    boundary: str  # what marked the start of the authority's part
    boundary_at: int  # character offset in the full order text
    truncated: bool


def find_boundary(order_text: str) -> tuple[int, str] | None:
    """Offset and marker of the earliest sign of the authority's part, or None."""
    found = [
        (m.start(), " ".join(m.group("head").split()))
        for rx in (HEADING_LINE, HEADING_INLINE, AUTHORITY_VOICE)
        if (m := rx.search(order_text))
    ]
    return min(found) if found else None


def split_facts(order_text: str) -> FactsSplit | None:
    b = find_boundary(order_text)
    if b is None:
        return None
    at, marker = b
    prefix = order_text[:at].rstrip()
    if len(prefix) < MIN_CHARS or DECISION.search(prefix):
        return None
    truncated = len(prefix) > MAX_CHARS
    gap = "\n[... part of the complainant's narrative omitted for length ...]\n"
    text = prefix[:HEAD_CHARS] + gap + prefix[-TAIL_CHARS:] if truncated else prefix
    return FactsSplit(text=text, boundary=marker, boundary_at=at, truncated=truncated)


def why_not(order_text: str) -> str:
    """Reason an order has no usable facts part (for coverage reports)."""
    b = find_boundary(order_text)
    if b is None:
        return "no start of the authority's part found"
    prefix = order_text[: b[0]]
    if len(prefix.strip()) < MIN_CHARS:
        return "facts part too short"
    if DECISION.search(prefix):
        return "decision wording before the cut"
    return "ok"
