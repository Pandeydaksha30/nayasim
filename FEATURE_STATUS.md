# Feature status (17 Nov 2026)

Update 17 Nov (ContractIQ): renamed from NyayaSim; contract clause analysis (rights, obligations,
penalties per party, the mid-viva eContractIQ feature) added and tested with a scripted model;
calculator audited and corrected (FINANCIAL_CALCULATOR_AUDIT.md); deployment moved to Vercel and
Render (configured, not deployed). 267 backend tests pass; live Gemini runs of the new clause
analysis have **not** been done yet.

Update 13 Nov: document RAG, agent orchestration, Ask and Agent pages added and verified live
(TEST_REPORT.md). Rows 6 to 10 below changed from Missing to verified.

Classes: **Working and verified** (run and checked, date given), **Implemented but untested**
(code exists, not exercised in a recorded check), **Partially implemented**, **Broken**,
**Missing**. Nothing is running at the moment of this audit, so "verified" refers to the dated
check. Update 12 Nov: the journey was re-run end to end and 49 of 49 checks passed
(docs/history/END_TO_END_TEST_REPORT.md).

## The requested demo journey

| # | Step | Status | Evidence / note |
|---|---|---|---|
| 1 | Open application | Working and verified (10 Nov, browser) | Servers are currently stopped |
| 2 | Register a new user | Working and verified (10 Nov, browser + tests) | No email provider: the verification link is read from `data/outbox/` |
| 3 | Log in | Working and verified (10 Nov, browser + tests) | Session cookie, not JWT |
| 4 | Upload a sample legal document | Working and verified (10 Nov) | PDF and images; limit 100 pages |
| 5 | Document is parsed | Working and verified (10 Nov) | Text layer or Tesseract OCR, per page |
| 6 | Chunks generated for the uploaded document | Working and verified (13 Nov, tests + live) | On upload; `case_document_chunks` (migration 0009) |
| 7 | Embeddings generated for the uploaded document | Working and verified (13 Nov) | Local bge-small, 384 dims; search mode "hybrid" in the live check |
| 8 | Uploaded document stored in a vector database | Working and verified (13 Nov) | pgvector column + HNSW index, per case |
| 9 | Ask a question about the uploaded document | Working and verified (13 Nov, live with Gemini) | Page "Ask your documents", `POST /cases/{id}/ask`; demo cases only, private cases get passages without a model |
| 10 | RAG retrieves relevant information | Working and verified (13 Nov) | 40-question set over fictional documents: recall@5 1.0, answers and citations 30/30 correct, 10/10 unanswerable refused. Small, easy set. |
| 11 | Source citations displayed | Working and verified (10 Nov) | Facts show document + page; hearing citations are checked against stored text |
| 12 | Run precedent search | Working and verified (13 Nov) | Page `/search` and `GET /api/v1/search/orders`; also runs inside the hearing |
| 13 | Start a hearing simulation | Working and verified (10 Nov, 1 completed run) | Demo cases only; depends on the Gemini free tier (slow, can fail) |
| 14 | Claim-type classification | Working and verified (13 Nov) for pasted order text | `POST /api/v1/predictions/order-text` and the `/search` page (74.3% on test). For a buyer's own case the buyer still picks the claim type. |
| 15 | Outcome prediction | Working and verified (13 Nov) | The report shows a rule-based estimate (`GET /api/v1/cases/{id}/estimate`, 72.9% on test) next to the precedent shares and the judge's finding |
| 16 | Log out and log in again | Working and verified (10 Nov, tests) | |

## Added 13 Nov

| Feature | Status | Evidence / note |
|---|---|---|
| Agent orchestration (LangGraph plan-act loop, 7 tools + delegate) | Working and verified (tests + 3 live runs) | Tool sequence chosen by the model; differs by objective |
| Specialist agents (document analysis, legal research, claim analysis) | Implemented and tested with a scripted model | Not chosen by Gemini in the live runs so far |
| Hearing and judge assessment inside the agent | Working and verified (13 Nov live) | Saved as a hearing run; 3 hearing citations verified in the agent answer |
| Execution limits, refusals, tracing, failure handling | Working and verified (tests) | 6 steps, 7 min, repeat refusal, once-only hearing, 2 model failures stop |
| Citation verification of agent answers | Working and verified | Code, not a model; D/O/H labels |
| User A cannot read user B's case, chunks, answers, runs | Working and verified (tests + e2e `isolation`, 9 checks) | 404 |
| Agent analysis page | Working (renders, live run shown) | `/cases/{id}/agent` |
| Docker images | Build verified 13 Nov | Never run on a public server |

## Other features

| Feature | Status | Evidence / note |
|---|---|---|
| Backend starts, `/health` | Working and verified (11 Nov) | Stopped now |
| Database connection, migrations to `0010` | Working and verified (13 Nov) | 0009 and 0010 reversible |
| Frontend to backend through the `/api` rewrite | Working and verified (10 Nov) | |
| Email verification, password reset | Working and verified (tests) | Links go to `data/outbox/`; real sending untested (no SMTP) |
| Google sign-in | Working and verified locally (13 Nov) | A real Google account signed in; test-user mode on Google's side |
| Rate limits, lockout, CSRF origin check, case ownership (404 for others) | Working and verified (tests) | No external security test yet |
| Account page (change password, delete account, sign out everywhere) | Working and verified (tests) | |
| Fact extraction from uploaded documents | Working and verified (10 Nov, demo case) | Demo cases only; blocked for real cases by the privacy rule |
| Fact confirmation, follow-up questions | Working and verified (10 Nov) | |
| Interest calculator (page and API) | Working and verified (tests) | Deterministic Python |
| Money and report pages of a case | Working and verified (12 Nov) | docs/history/END_TO_END_TEST_REPORT.md |
| Complaint draft page | Working and verified (13 Nov) | Built by code from verified facts and verified citations; blanks where something is unknown |
| Citation verifier | Working and verified (benchmark) | Precision 100%, recall 98.3% on held-out orders |
| Order ingestion and OCR | Working and verified | 2,209 orders with text; latest download stopped at about 190 of 1,000 |
| Embedding of order chunks | Partially implemented | 65,974 of 72,970 chunks embedded |
| Classifier training and evaluation scripts | Working and verified (11 Nov) | Offline |
| Prediction API endpoints | Working and verified (13 Nov) | Estimate and classifier demo |
| Deployment: Vercel (website) + Render native Python (API) + Render PostgreSQL | Configured, not deployed (17 Nov) | `render.yaml`, `frontend/vercel.json`, DEPLOYMENT_GUIDE.md. The earlier Docker stack was removed |
| Public deployment | **Missing** | No server, no public URL |
| Invalid file, empty upload, unsupported format handling | Implemented but untested in this audit | Unit tests cover some cases; to be exercised in Phase 4 |

## Broken

Nothing was found broken by reading the code. This will be confirmed or corrected by actually
running the journey in Phase 4.
