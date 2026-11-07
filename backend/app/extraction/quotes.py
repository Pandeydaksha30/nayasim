"""Find a model's quote in the stored page text and return exact character offsets.

1. Exact match, ignoring only whitespace and letter case (models re-flow line breaks).
2. Otherwise, for quotes of at least FUZZY_MIN_CHARS, a near match: the best-aligned span of
   the page must be >= FUZZY_MIN_SCORE similar. This tolerates a model silently fixing an
   OCR typo ("alreacly" -> "already") but not a paraphrase.

Either way the returned span points at the *stored* text. Callers must read values from
that stored span, never from the model's quote, so a "corrected" number cannot slip in.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

MIN_QUOTE_CHARS = 6
FUZZY_MIN_CHARS = 25
FUZZY_MIN_SCORE = 90.0


@dataclass(frozen=True)
class Span:
    char_start: int
    char_end: int
    match: str = "exact"  # "exact" or "fuzzy:<score>"


def _normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace runs to one space and lowercase; keep each output char's source index."""
    out: list[str] = []
    index: list[int] = []
    in_space = False
    for i, ch in enumerate(text):
        if ch.isspace() or ch == "﻿":
            if not in_space and out:
                out.append(" ")
                index.append(i)
            in_space = True
        else:
            out.append(ch.lower())
            index.append(i)
            in_space = False
    if out and out[-1] == " ":
        out.pop()
        index.pop()
    return "".join(out), index


def _to_span(index: list[int], start: int, end: int, match: str, text: str) -> Span:
    # Trim spaces at the edges of the aligned window so the stored span starts/ends on text.
    a, b = index[start], index[end - 1] + 1
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    return Span(a, b, match)


def locate(quote: str, page_text: str) -> Span | None:
    """Offsets of ``quote`` in ``page_text``, or None if it is not there closely enough."""
    q, _ = _normalise_with_map(quote or "")
    if len(q) < MIN_QUOTE_CHARS:
        return None
    norm, index = _normalise_with_map(page_text)
    pos = norm.find(q)
    if pos != -1:
        return _to_span(index, pos, pos + len(q), "exact", page_text)
    if len(q) < FUZZY_MIN_CHARS or not norm:
        return None
    al = fuzz.partial_ratio_alignment(q, norm, score_cutoff=FUZZY_MIN_SCORE)
    if al is None or al.dest_end <= al.dest_start:
        return None
    return _to_span(index, al.dest_start, al.dest_end, f"fuzzy:{al.score:.1f}", page_text)
