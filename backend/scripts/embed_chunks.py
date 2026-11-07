"""Compute embeddings for order chunks with a local model (nothing leaves the computer).

Usage (from backend/):
  .\\.venv\\Scripts\\python.exe -m scripts.embed_chunks --limit 2000
  .\\.venv\\Scripts\\python.exe -m scripts.embed_chunks --benchmark 200 --model BAAI/bge-small-en-v1.5

Resumable: only chunks without an embedding from this model are processed. Each batch is
committed, and the model name is stored with every vector.
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import EMBEDDING_DIM
from app.db.session import get_engine
from app.retrieval.embedder import LocalEmbedder


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=settings.embedding_model)
    ap.add_argument("--limit", type=int, default=0, help="embed up to N chunks")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument(
        "--benchmark", type=int, default=0, metavar="N", help="time N chunks without writing anything"
    )
    args = ap.parse_args()

    t0 = time.monotonic()
    embedder = LocalEmbedder(args.model, settings.embedding_query_prefix, settings.embedding_doc_prefix)
    print(f"model {embedder.name}: dim {embedder.dim}, loaded in {time.monotonic() - t0:.1f} s")

    engine = get_engine()
    if args.benchmark:
        with engine.connect() as c:
            texts = [
                r[0]
                for r in c.execute(
                    text("SELECT text FROM order_chunks ORDER BY id LIMIT :n"), {"n": args.benchmark}
                )
            ]
        t = time.monotonic()
        embedder.embed_documents(texts)
        dt = time.monotonic() - t
        total = engine.connect().execute(text("SELECT count(*) FROM order_chunks")).scalar()
        per = dt / max(1, len(texts))
        print(
            f"benchmark: {len(texts)} chunks in {dt:.1f} s = {per * 1000:.0f} ms per chunk; "
            f"{total} stored chunks would take {total * per / 60:.0f} min"
        )
        return 0

    if embedder.dim != EMBEDDING_DIM:
        print(
            f"model dimension {embedder.dim} does not match the database column ({EMBEDDING_DIM}); "
            "a migration is needed first"
        )
        return 2
    done = 0
    t = time.monotonic()
    while not args.limit or done < args.limit:
        size = args.batch if not args.limit else min(args.batch, args.limit - done)
        with Session(engine) as s:
            rows = s.execute(
                text("""SELECT id, text FROM order_chunks
                        WHERE embedding_model IS DISTINCT FROM :m ORDER BY id LIMIT :n"""),
                {"m": embedder.name, "n": size},
            ).all()
            if not rows:
                break
            vectors = embedder.embed_documents([r[1] for r in rows])
            for (cid, _), vec in zip(rows, vectors, strict=True):
                s.execute(
                    text(
                        "UPDATE order_chunks SET embedding = CAST(:v AS vector), embedding_model = :m "
                        "WHERE id = :id"
                    ),
                    {"v": str(vec), "m": embedder.name, "id": cid},
                )
            s.commit()
        done += len(rows)
        rate = done / (time.monotonic() - t)
        print(f"embedded {done} chunks ({rate:.1f}/s)", flush=True)
    print(f"done: {done} chunks in {(time.monotonic() - t) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
