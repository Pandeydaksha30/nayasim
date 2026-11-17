# ContractIQ

**Real-estate contract intelligence and legal dispute support.** A home buyer uploads their
builder–buyer agreement and papers; ContractIQ answers questions about the contract with the
clause and page, lists each party's rights and obligations, extracts and verifies the key facts,
computes what the buyer is owed, retrieves real precedents from public RERA orders, simulates a
hearing with advocate, defence and judge agents, and drafts the complaint and report.

The rule throughout: **nothing is shown unless it can be traced to a source.** Every answer,
clause, fact and citation is checked by code against the stored document or order, and all money
is calculated by deterministic code, never by the language model.

ContractIQ began as eContractIQ (mid-viva: contract Q&A and benefits/obligations analysis). How it
grew, and what is new versus carried over: **PROJECT_EVOLUTION.md**.

**Status (17 Nov 2026):** runs locally end to end; 267 backend tests pass. Deployment to Vercel
(website) and Render (API and PostgreSQL) is configured but **not yet deployed**.

## Features

| Feature | Where |
|---|---|
| Upload PDFs and images; text layer read locally, OCR for scans (locally) | `backend/app/buyer/documents.py` |
| **Ask your contract**: retrieval over the case's own documents (pgvector), answers with verified quotes, or "not enough in the documents" | `backend/app/rag/answer.py` |
| **Contract analysis**: rights, obligations, penalties and one-sided terms of each party, every clause quoted and checked | `backend/app/rag/clauses.py` |
| Fact extraction with page and quote; the buyer confirms; unconfirmed facts are never used later | `backend/app/buyer/facts.py` |
| **Financial claim calculator**: delay interest and refund, deterministic, audited | `backend/app/calculator/interest.py`, `FINANCIAL_CALCULATOR_AUDIT.md` |
| Legal precedent retrieval over 2,209 HRERA Gurugram orders (~73,000 passages), keyword + vector | `backend/app/retrieval/search.py` |
| Citation verification (precision 100%, recall 98.3% on held-out orders) | `backend/app/verifier/citations.py` |
| Simulated hearing: buyer's advocate, builder's advocate (defence), citation gate, judge | `backend/app/hearing/graph.py` |
| Agent analysis: the model chooses tools and specialist agents, bounded, every step saved | `backend/app/agent/` |
| Report with outcome estimate and weak points; complaint draft built from verified facts | `backend/app/insights/` |
| Accounts, email confirmation, Google sign-in, per-user isolation, rate limits | `backend/app/auth/` |

## Technology

Next.js 15 / React 19 / TypeScript (Vercel); FastAPI on Python 3.12 (Render); PostgreSQL 17 with
pgvector (Render PostgreSQL); local `bge-small-en-v1.5` embeddings (fastembed); Tesseract OCR;
LangGraph; Google Gemini; scikit-learn.

## Run, demonstrate, deploy

| | |
|---|---|
| Run locally | **RUN_LOCAL.md** (website http://localhost:3100, API http://localhost:8000/docs) |
| Demonstration script | **DEMO_GUIDE.md**, fictional documents in `demo/sample-documents/` |
| Deploy | **DEPLOYMENT_GUIDE.md** (`render.yaml`, `frontend/vercel.json`) |

## Measured results

| Component | Result | Note |
|---|---|---|
| Citation checker | Precision 100%, recall 98.3% | held-out orders |
| Document Q&A (40 questions over fictional documents) | 30/30 correct with correct citation; 10/10 unanswerable refused | small, easy set |
| Outcome prediction, best method (claim × delay rule) | 72.9% | exploratory |
| Claim type (relief-section rule + model) | 74.3%, macro-F1 0.455 | exploratory |

Outcome labels were extracted by a model and have not been checked by people; see
`MODEL_EVALUATION.md` before quoting a prediction figure.

## Privacy

Text of a case is sent to the language model only for cases marked as fictional demos, because the
model tier in use may retain data; the API refuses real cases (HTTP 403) until a no-retention model
is configured. Retrieval and the calculator run on the server for every case.

## Documentation

| File | Content |
|---|---|
| `PROJECT_EVOLUTION.md` | Problem statement; mid-viva vs intermediate vs final comparison |
| `ARCHITECTURE.md` | Design and data flow |
| `FINANCIAL_CALCULATOR_AUDIT.md` | Formulas, legal sources, sample cases, limitations |
| `API_DOCUMENTATION.md` | Endpoints |
| `SECURITY.md` | Security controls and gaps |
| `FEATURE_STATUS.md`, `TEST_REPORT.md` | What works and how it was tested |
| `MODEL_EVALUATION.md`, `MODEL_TRAINING_GUIDE.md` | Prediction models |
| `docs/` | Component notes; `docs/history/` holds earlier reports and the mid-viva code |

## Project layout

```text
backend/    FastAPI app (app/), migrations, tests, eval set, scripts, uv.lock
frontend/   Next.js website, vercel.json
infra/      local development database (docker-compose.yml), data export/import scripts
data/       classifier files (tracked); uploads, outbox, model cache (not tracked)
release/    public order data file for import (not tracked)
benchmark/  frozen evaluation split
demo/       fictional sample documents
docs/       component notes and history
scripts/    local start scripts (PowerShell)
render.yaml Render blueprint
```

## Limits

Decision support, not legal advice. Prediction is not reliable enough to act on. Orders cover one
authority (HRERA Gurugram).
