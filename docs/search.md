# Search over past orders (step 6)

`app/retrieval/search.py` — `search(session, query, before=<date>, embedder=...)`.

## Rules

* **Cutoff is mandatory.** Only orders decided strictly before `before` are searched (the
  time-split backtest depends on it). The SQL filters on `decided_on`, and every hit is
  checked again in Python; a later order reaching the results raises `CutoffLeak` instead of
  being dropped quietly. Calling `search` without a date raises `TypeError`.
* **Keyword search:** Postgres full text with English stemming (migration 0004: "possessed"
  matches "possession"); content words of the query are OR-ed and ranked by `ts_rank_cd`.
* **Vector search:** cosine distance in pgvector, using only vectors from the configured model
  (`order_chunks.embedding_model`). If none exist yet, search falls back to keyword only and
  says so in `notes`.
* **Fusion:** Reciprocal Rank Fusion, `score = Σ 1/(60 + rank)` over the two lists.
* At most 2 passages per order, so one long order cannot fill the results.
* Every hit carries order, decision date, page and exact character offsets of stored text.

## Embedding model

Computed **locally** (fastembed, CPU), because search queries will be built from buyers'
private facts. Model files are cached in `data/models` (git-ignored).

Measured on 200 real passages, with the OCR fetch running on the same CPU (absolute times
inflated, comparison valid): `bge-small-en-v1.5` 266 ms/passage, `bge-base-en-v1.5`
1,254 ms/passage; `bge-large-en-v1.5` was slower still and the run was stopped. Chosen:
**`BAAI/bge-small-en-v1.5`** (384 dimensions, migration 0005). Orders are English; keyword
search covers exact legal terms. Retrieval quality is to be measured in the backtest, not assumed.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.embed_chunks --limit 5000      # resumable, batches of 64
.\.venv\Scripts\python.exe -m scripts.embed_chunks --benchmark 200 --model BAAI/bge-base-en-v1.5
```

First run: 640 passages embedded at 1.5/s (OCR running alongside). Two real queries with a
1 Jan 2025 cutoff returned relevant passages (force-majeure/NGT/COVID pleas and their
rejection; refund with interest under section 18), all decided before the cutoff, with
results from both keyword-only and vector-only matches.
