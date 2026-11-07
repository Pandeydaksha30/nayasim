"""Text embedders. Embeddings are computed locally so a buyer's facts used as a search query
never leave the computer.

`HashingEmbedder` is a deterministic bag-of-words stand-in used by tests (and as a fallback
nowhere else). `LocalEmbedder` wraps a fastembed ONNX model chosen by measurement.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from app.db.models import EMBEDDING_DIM


class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


_WORD = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    """Deterministic: each word adds to a hashed dimension; vectors are L2-normalised.
    Texts that share words are close. For tests only."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim
        self.name = f"hashing-{dim}"

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for w in _WORD.findall(text.lower()):
            h = int.from_bytes(hashlib.blake2b(w.encode(), digest_size=8).digest(), "big")
            v[h % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class LocalEmbedder:
    """fastembed (ONNX, CPU). Model files are downloaded once and cached locally."""

    def __init__(self, model: str, query_prefix: str = "", doc_prefix: str = "") -> None:
        from pathlib import Path

        from fastembed import TextEmbedding

        # Kept in the project's git-ignored data/models so the download happens once.
        cache = Path(__file__).resolve().parents[3] / "data" / "models"
        self._model = TextEmbedding(model_name=model, cache_dir=str(cache))
        self.name = f"fastembed:{model}"
        self.query_prefix, self.doc_prefix = query_prefix, doc_prefix
        self.dim = len(next(iter(self._model.embed(["dimension probe"]))))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed([self.doc_prefix + t for t in texts])]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.embed([self.query_prefix + text]))).tolist()
