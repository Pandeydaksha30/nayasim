# NyayaSim architecture (13 Nov 2026)

Current system. (`architecture/ARCHITECTURE.md` describes the earlier ContractIQ prototype with
ChromaDB and Groq and is kept only for history.)

```text
Browser ── Next.js 15 (frontend/, port 3100) ── /api rewrite ──▶ FastAPI (backend/, port 8000)
                                                                      │
        ┌───────────────┬───────────────┬──────────────┬──────────────┼────────────────┐
        ▼               ▼               ▼              ▼              ▼                ▼
   auth/ (sessions) buyer/ (upload,  rag/ + retrieval/ agent/ (LangGraph hearing/ (LangGraph  insights/, ml/,
                    OCR, facts,      case_search      orchestrator,    buyer → builder →   calculator/
                    chunks)          (per-case RAG)   tools, verify)   gate → judge)
        └───────────────┴──────── PostgreSQL 17 + pgvector (infra/docker-compose.yml) ────────┘
                                         Gemini (only for demo cases) ◀── model calls
```

## Data flow: a buyer's document

1. **Upload** (`POST /cases/{id}/documents`, `app/buyer/documents.py`): PDF or image, ≤100 pages.
   Text layer read with pypdfium2; scanned pages go through Tesseract OCR. Pages stored in
   `case_document_pages`.
2. **Index** (`app/buyer/chunks.py`): each page split by the same chunker used for public orders
   (`app/ingestion/chunker.py`, sentence boundaries, character offsets kept), embedded locally
   with `BAAI/bge-small-en-v1.5` (384 dims, fastembed), stored in `case_document_chunks`
   (pgvector + generated tsvector). Runs in the upload request; nothing leaves the server.
3. **Facts** (`app/buyer/facts.py`): the model proposes fields with a quote; code checks every quote
   against the page (and a database trigger checks it again). Demo cases only.

## Document question answering (RAG)

`app/retrieval/case_search.py`: hybrid search, keyword (Postgres full text) plus vector (cosine),
fused by reciprocal rank. The case id is part of every SQL statement and every returned row is
re-checked against it (`CaseLeak`).
`app/rag/answer.py`: the model sees only the labelled passages [D1]… and must answer in a schema
with exact quotes. **Code** then checks each quote against the stored passage (`extraction/quotes.locate`)
and requires every number to match exactly. No verified citation, or the model says the passages
are insufficient → "The uploaded documents do not contain enough to answer this question."
Endpoints: `GET /passages` (no model, all cases), `POST /ask` (demo cases), `GET /questions` (history).

## Agent orchestration (`app/agent/`)

A LangGraph graph `plan → act → plan … → answer → verify`:

- **plan**: the model returns one `Step` (a tool and its arguments, or `finish`). Nothing in the code
  fixes the order of tools; the tool sequence differs by objective (see TEST_REPORT.md, live runs).
- **act**: code runs the tool; the result (or the error) becomes an observation.
- **answer**: the model writes the answer from the observations only, citing evidence labels.
- **verify**: code checks every citation: D-labels against document passages, O-labels and
  H-labels (hearing citations) against the stored order page with `app/verifier/citations.py`.

Tools: `search_documents`, `get_facts`, `search_orders`, `verify_quote`, `calculate_interest`
(deterministic calculator), `estimate_outcome` (rule-based, 72.9% on test), `run_hearing` (the
existing hearing graph; the result is also saved as a hearing run), `delegate`.

Specialised agents are the same loop with a narrower tool set and 3 steps:
`document_analysis` (documents, facts), `legal_research` (orders, may reformulate the query),
`claim_analysis` (facts, interest, outcome estimate). The hearing (buyer advocate, builder advocate,
citation gate, judge) is the existing fixed pipeline, reached as a tool.

Limits enforced by code: 6 steps (orchestrator), 3 (specialists), 7-minute wall clock, identical
repeated calls refused, `run_hearing` at most once, two model failures in a row end the run, a
LangGraph recursion limit as a second bound. Every step is saved to `agent_runs.steps` as it
happens (tool, arguments, reason, observation, ok, milliseconds).

Background execution: `app/agent/jobs.py` (thread pool, same pattern as hearings); runs left
`running` by a restart are marked failed at startup.

## Machine learning

- Outcome estimate: claim type × delay rule over past orders (`app/insights/estimate.py`), shown on
  the report and used by the agent tool. 72.9% on held-out orders.
- TF-IDF + logistic regression classifiers (`data/models/*.joblib`) for pasted order text
  (`POST /predictions/order-text`). Not applied to a buyer's own agreement: they are trained on
  orders, and applying them to agreements would be outside what they were measured on.
- The frozen benchmark split (`benchmark/`) is untouched by this work.

## Database migrations (`backend/migrations/versions/`)

0001–0008 existing; **0009** `case_document_chunks`, `case_questions`; **0010** `agent_runs`.
All new migrations have a `downgrade()` that drops only the new tables.

## Privacy rule

Text of a case is sent to the model (Gemini) only when the case is a fictional demo, or when
`NYAYASIM_PRIVATE_LLM_OK=true` is set after a zero-retention provider is configured. Retrieval
(`/passages`) is local and works for every case.
