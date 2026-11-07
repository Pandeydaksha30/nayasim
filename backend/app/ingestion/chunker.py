"""Split page text into retrieval chunks whose offsets are exact.

Each chunk is ``page_text[char_start:char_end]`` — no rewriting, no joining — so any
citation built on a chunk can be checked character for character against the stored
page. Chunks prefer to end at a paragraph break, then a sentence end, then a space.
"""

from __future__ import annotations

from dataclasses import dataclass

TARGET_CHARS = 1000
MIN_CHARS = 400
MAX_CHARS = 1400


@dataclass(frozen=True)
class Chunk:
    char_start: int
    char_end: int
    text: str


def _best_break(text: str, start: int, hard_end: int) -> int:
    window_lo = start + MIN_CHARS
    for sep in ("\n\n", ". ", "।", "\n", " "):  # "।" is the Devanagari full stop
        cut = text.rfind(sep, window_lo, hard_end)
        if cut != -1:
            return cut + len(sep)
    return hard_end


def chunk_page(text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    n = len(text)
    start = 0
    while start < n:
        # Skip leading whitespace so chunks don't start blank.
        while start < n and text[start].isspace():
            start += 1
        if start >= n:
            break
        if n - start <= MAX_CHARS:
            end = n
        else:
            end = _best_break(text, start, min(start + TARGET_CHARS + (MAX_CHARS - TARGET_CHARS) // 2, n))
        # Trim trailing whitespace inside the chunk while keeping offsets exact.
        trimmed = end
        while trimmed > start and text[trimmed - 1].isspace():
            trimmed -= 1
        chunks.append(Chunk(start, trimmed, text[start:trimmed]))
        start = end
    return chunks
