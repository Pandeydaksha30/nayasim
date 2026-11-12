# NyayaSim

Before a home buyer files a RERA complaint against a builder, NyayaSim reads their papers, works
out what they are owed, and simulates a hearing argued from real orders of the Haryana Real Estate
Regulatory Authority (Gurugram). Every fact is tied to a page, every citation is checked against
the stored order, and all money is calculated by ordinary code.

**Status (12 Nov 2026):** runs locally end to end; 49 of 49 end-to-end checks and all 224 unit tests
pass (END_TO_END_TEST_REPORT.md). **Not deployed to a public address.** Accuracy figures are
reported as measured and are modest; labels have not yet been checked by people.

## What it does

| Feature | State | Where |
|---|---|---|
| Accounts: sign-up, email confirmation, login, password reset, account deletion | Working | `backend/app/auth/`, `docs/accounts.md` |
| Upload of PDFs and images, text read locally (OCR for scans) | Working | `backend/app/buyer/documents.py` |
| Facts read from the documents, each with page and quote, confirmed by the buyer | Working (fictional demo cases only, see Privacy) | `docs/buyer-documents.md` |
| Delay interest and refund calculator | Working | `backend/app/calculator/` |
| Search over 2,209 public orders: keyword + vector, with a decision-date cutoff | Working, used inside the hearing | `docs/search.md` |
| Citation checker | Working; precision 100%, recall 98.3% on held-out orders | `docs/citations.md` |
| Simulated hearing (buyer advocate, builder advocate, citation gate, judge) and report | Working (demo cases only) | `docs/hearing.md` |
| Trained classifiers for outcome and claim type | Offline scripts only | `MODEL_TRAINING_GUIDE.md` |
| Google sign-in | Coded, not configured, untested against Google | `docs/accounts.md` |
| Complaint draft | Placeholder page | |
| Production stack (Docker Compose + Caddy) | Written, never run on a public server | `docs/deploy.md`, `DEPLOYMENT_CHECKLIST.md` |

Not part of the system: question-answering over an uploaded document, embeddings of uploaded
documents, API endpoints for the trained classifiers, a standalone precedent search page.

## Technology

Next.js 15 / React 19 / TypeScript; FastAPI on Python 3.12; PostgreSQL 17 with pgvector; local
`bge-small` embeddings (fastembed); Tesseract OCR; LangGraph; Google Gemini (free tier);
scikit-learn. Sessions are server-side with an HttpOnly cookie (not JWT).

## Run it

Exact commands, addresses and troubleshooting: **RUN_LOCAL.md**.
Website http://localhost:3100, API documentation http://localhost:8000/docs.

## Demonstrate it

**DEMO_GUIDE.md**: a 5 to 7 minute sequence, sample fictional documents in
`demo/sample-documents/`, and what to do if the model is unavailable.

## Measured results (held-out test orders)

| Component | Result |
|---|---|
| Citation checker | Precision 100%, recall 98.3% |
| Outcome prediction, best method (claim x delay rule) | 72.9% |
| Outcome prediction, language model with the parties' filings | 67.8%, macro-F1 0.653 |
| Outcome prediction, trained classifier | 50.8% |
| Claim type, relief-section rule plus trained model | 74.3%, macro-F1 0.455 |

Details and method: `MODEL_EVALUATION.md`, `MODEL_TRAINING_GUIDE.md`, `AGENT_STATUS.md`.

## Privacy

Uploaded documents stay on the machine. Text is sent to the language model only for cases marked
as fictional demos, because the free model tier may retain data; the API refuses real cases
(HTTP 403) until a zero-retention model is configured. `backend/.env` and `data/` are never
committed.

## Documents

| File | Content |
|---|---|
| `PROJECT_AUDIT.md` | Components, routes, configuration, current state |
| `FEATURE_STATUS.md` | Each feature: verified, untested, partial, missing |
| `RUN_LOCAL.md` | Start-up commands |
| `END_TO_END_TEST_REPORT.md` | Test results of 12 Nov 2026 |
| `DEMO_GUIDE.md` | Demonstration script |
| `DEPLOYMENT_CHECKLIST.md` | What a public deployment needs |
| `HANDOFF.md` | Project rules and history |

## Limits

This is a preparation aid, not legal advice. Outcome prediction is not reliable enough to act on.
Data covers one authority (HRERA Gurugram).
