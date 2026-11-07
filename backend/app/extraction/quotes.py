"""Find a model's quote in the stored page text and return exact character offsets.

Matching ignores differences in whitespace and letter case only (models re-flow line
breaks). Anything else — a corrected OCR error, a paraphrase, an ellipsis — does not
match, and the field is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_QUOTE_CHARS = 6


@dataclass(frozen=True)
class Span:
    char_start: int
    char_end: int


def _normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace runs to one space and lowercase; keep each output char's source index."""
    out: list[str] = []
    index: list[int] = []
    in_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
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


def locate(quote: str, page_text: str) -> Span | None:
    """Offsets of ``quote`` in ``page_text`` (first occurrence), or None if it is not there."""
    q, _ = _normalise_with_map(quote)
    if len(q) < MIN_QUOTE_CHARS:
        return None
    norm, index = _normalise_with_map(page_text)
    pos = norm.find(q)
    if pos == -1:
        return None
    return Span(index[pos], index[pos + len(q) - 1] + 1)
