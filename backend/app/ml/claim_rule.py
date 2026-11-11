"""Claim type read from the "relief sought" section of an order's parties' part.

Why a rule: across the whole text "refund" is boilerplate (85 of 178 delay orders in training say
it), but inside the relief section it states the claim. Developed on train and validation orders
only (MODEL_TRAINING_GUIDE.md). Returns None when there is no relief section or no clear wording;
the caller then falls back to the trained model.
"""

from __future__ import annotations

import re

from app.backtest.facts import RELIEF_HEAD

WINDOW = 700  # characters read after each relief heading
REFUND = re.compile(
    r"re[ft]und|return\s+(?:of\s+)?the\s+(?:entire\s+|paid\s+|deposited\s+)?amount", re.IGNORECASE
)
DELAY = re.compile(
    r"dela\w*\s+poss|poss\w*\s+charges|d\.?p\.?c\b"
    r"|hand\s*over\s+(?:the\s+)?(?:physical\s+)?possession"
    r"|interest\s+(?:for|on)\s+(?:every\s+month\s+of\s+|the\s+)?delay"
    r"|deliver\w*\s+(?:of\s+)?(?:the\s+)?possession",
    re.IGNORECASE,
)

TABLE_INTRO = re.compile(r"\s*(?:is|are)\s+given\s+in\s+the\s+ta", re.IGNORECASE)


def relief_claim(text: str) -> str | None:
    """'refund', 'delayed_possession' or None. When both are asked for, the first one wins."""
    # "... and relief sought are given in the table below" introduces a table of unit details in
    # batch orders, not the relief itself.
    heads = [m for m in RELIEF_HEAD.finditer(text) if not TABLE_INTRO.match(text, m.end())]
    if not heads:
        return None
    window = " ".join(text[m.end() : m.end() + WINDOW] for m in heads)
    refund, delay = REFUND.search(window), DELAY.search(window)
    if refund and delay:
        return "refund" if refund.start() < delay.start() else "delayed_possession"
    return "refund" if refund else "delayed_possession" if delay else None
