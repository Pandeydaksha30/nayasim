"""Choose which pages of an order to send to the model.

HRERA orders put the facts table (due date, sale consideration, amount paid) in the first
pages and the decision and directions in the last pages; the middle is mostly arguments and
quoted case law. Sending only the useful pages makes each call several times faster and
cheaper. Page numbers are kept, so quotes are still verified against the full stored order.

Selection: the first FIRST pages and last LAST pages always; then other pages that mention
key terms, highest-scoring first; all within MAX_CHARS. If even the always-pages exceed the
budget they are still sent whole (a page is never cut, so quotes stay verifiable).
"""

from __future__ import annotations

import re

FIRST = 3
LAST = 3
MAX_CHARS = 24_000

KEY_TERMS = [
    re.compile(p, re.I)
    for p in (
        r"due date of (?:handing over )?possession",
        r"(?:total )?(?:sale )?consideration",
        r"amount paid|paid by the complainants?",
        r"prescribed rate",
        r"\b\d{1,2}(?:\.\d+)?\s*%",
        r"directions? (?:of|issued by|under)",
        r"\b(?:is|are|stands?) (?:hereby )?(?:allowed|dismissed|disposed)",
        r"\brefund\b",
        r"delay(?:ed)? possession charges",
    )
]


def _score(text: str) -> int:
    return sum(len(p.findall(text)) for p in KEY_TERMS)


def select_pages(pages: dict[int, str], max_chars: int = MAX_CHARS) -> dict[int, str]:
    if not pages:
        return {}
    numbers = sorted(pages)
    always = set(numbers[:FIRST]) | set(numbers[-LAST:])
    chosen = {n: pages[n] for n in numbers if n in always}
    used = sum(len(t) for t in chosen.values())
    candidates = sorted((n for n in numbers if n not in always), key=lambda n: (-_score(pages[n]), n))
    for n in candidates:
        if _score(pages[n]) == 0:
            break
        if used + len(pages[n]) > max_chars:
            continue
        chosen[n] = pages[n]
        used += len(pages[n])
    return dict(sorted(chosen.items()))
