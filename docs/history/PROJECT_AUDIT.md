# Project audit (12 Nov 2026)

Read-only inspection of the repository and the local machine. No code was changed. Branch
`nyayasim/foundation`, last commit `e9d1271`, working tree clean before this audit.

## 1. What the project is

NyayaSim: a simulator for Haryana RERA (Gurugram) buyer disputes. A buyer uploads their papers,
confirms the facts read from them, and gets a simulated hearing argued from real, public HRERA
orders, with every citation checked against the stored text. The older "ContractIQ" code is kept
in `legacy/` and is not used.

## 2. Components

| # | Area | What exists | Entry point |
|---|---|---|---|
| 1 | Frontend | Next.js 15.5.4 (App Router), React 19, TypeScript, plain CSS. No UI library. | `frontend/app/layout.tsx`, `frontend/app/page.tsx`; dev `npm run dev` (port 3100) |
| 2 | Backend | FastAPI 0.118 on uvicorn, Python 3.12, SQLAlchemy, Alembic | `backend/app/main.py` (`app.main:app`, port 8000) |
| 3 | Database | PostgreSQL 17 with pgvector 0.8 in Docker, bound to 127.0.0.1:5432. URL in `backend/app/config.py` (`database_url`), overridable by environment. 15 tables, migration head `0008`. | `infra/docker-compose.yml` |
| 4 | API | 30 routes, listed below. Interactive docs at `/docs` (FastAPI default). | `backend/app/api/` |
| 5 | Auth | Email + password (Argon2id), email verification and reset links, optional Google sign-in (OIDC + PKCE). **Server-side sessions in an HttpOnly cookie, not JWT.** Rate limits, lockout, CSRF origin check, per-user case ownership, audit log. | `backend/app/auth/`, `backend/app/api/auth.py`, `backend/app/middleware.py`, `frontend/middleware.ts` |
| 6 | Upload and parsing | PDF / image upload to `data/uploads/<case>/`; text from the PDF text layer or Tesseract OCR, stored per page. Max 100 pages, 2 parallel uploads. | `backend/app/buyer/documents.py`, `POST /api/v1/cases/{id}/documents` |
| 7 | Retrieval (the "RAG" part) | Public orders are chunked (`ingestion/chunker.py`), embedded locally with fastembed `BAAI/bge-small-en-v1.5`, stored in Postgres/pgvector (`order_chunks`). Search is hybrid: Postgres full text + vector, fused by reciprocal rank, always limited to orders before a cutoff date. **There is no separate vector database** (no Chroma, Pinecone etc.). | `backend/app/retrieval/` |
| 8 | Precedent search and hearing | The hearing builds a search query from the case, retrieves precedents, and runs a LangGraph graph: buyer advocate, builder advocate, citation gate, judge, report. Runs as a background job; the page polls. | `backend/app/hearing/`, `POST /api/v1/cases/{id}/hearing` |
| 9 | ML models | TF-IDF + logistic regression for outcome and claim type, plus a relief-section rule. Artifacts in `data/models/*.joblib`. **Used only by offline scripts; no API endpoint serves them.** | `backend/app/ml/`, `backend/scripts/train_classifier.py` |
| 10 | Config and deployment | Settings from environment / `backend/.env` (git-ignored; holds the Gemini key). Production: Docker Compose with Caddy for HTTPS (`infra/docker-compose.prod.yml`, `infra/deploy.sh`, `infra/.env.prod.example`). | `backend/app/config.py`, `infra/` |

Other parts: deterministic interest calculator (`backend/app/calculator/`), citation verifier
(`backend/app/verifier/`), order ingestion from the HRERA site (`backend/app/ingestion/`), field
extraction from orders with Gemini (`backend/app/extraction/`), benchmark and backtest tools.

## 3. API routes

| Group | Routes |
|---|---|
| Health | `GET /health` |
| Auth (`/api/v1/auth`) | `GET /config`, `POST /signup`, `POST /verify-email`, `POST /resend-verification`, `POST /login`, `POST /logout`, `POST /logout-all`, `POST /forgot-password`, `POST /reset-password`, `GET /me`, `PATCH /me`, `POST /change-password`, `DELETE /me`, `GET /google/start`, `GET /google/callback` |
| Cases (`/api/v1/cases`) | `GET ""`, `POST ""`, `GET /{id}`, `POST /{id}/documents`, `GET /{id}/documents/{doc}/pages/{n}`, `POST /{id}/facts/extract`, `POST /{id}/facts/{fact}/confirm`, `PUT /{id}/answers/{question}` |
| Hearing (`/api/v1/cases`) | `POST /{id}/hearing` (202), `GET /{id}/hearing/runs/{run}`, `GET /{id}/hearing/active`, `GET /{id}/hearing` |
| Calculator | `POST /api/v1/calculations/interest` |

Not present: a question-answering endpoint over an uploaded document, a standalone precedent
search endpoint, and prediction endpoints for the trained classifiers.

## 4. Frontend pages

`/` (landing), `/signup`, `/login`, `/verify-email`, `/forgot-password`, `/reset-password`,
`/account`, `/dashboard`, `/cases/new`, `/cases/[id]` with `documents`, `facts`, `questions`,
`money`, `hearing`, `report`, `draft`, plus `/calculator`, `/method`, `/terms`, `/privacy`.
The browser calls `/api/...` on the site's own address; Next.js forwards it to the backend
(`API_URL` in `frontend/next.config.ts`), so the session cookie is same-origin.

## 5. Environment variables

| Name | Purpose | State |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini (free tier) | Set in `backend/.env`. **Was pasted in chat twice: rotate it.** |
| `NYAYASIM_DATABASE_URL` | Postgres URL | Default points at the local Docker database |
| `NYAYASIM_ALLOW_DEMO_CASES` | Allows fictional demo cases, the only cases whose text may go to Gemini | Off by default; `scripts/dev-api.ps1 -AllowDemo` turns it on |
| `NYAYASIM_PRIVATE_LLM_OK` | Would allow real documents to go to the model | Must stay `false` (the free tier can retain data) |
| `NYAYASIM_PUBLIC_URL`, `NYAYASIM_CORS_ORIGINS`, `COOKIE_SECURE` | Site address, allowed origins, HTTPS-only cookie | Local defaults; set in `infra/.env.prod.example` for production |
| `NYAYASIM_GOOGLE_CLIENT_ID` / `_SECRET` | Google sign-in | Not set: the Google button is hidden |
| `NYAYASIM_SMTP_*` | Outgoing email | Not set: verification and reset emails are written to `data/outbox/` instead of being sent |
| `API_URL` (frontend) | Where Next.js forwards `/api` | Defaults to `http://127.0.0.1:8000` |

`.env` files and `data/` are git-ignored. No secret was found in tracked files during this audit
(names only were inspected; values were not printed).

## 6. State of the machine right now

| Item | State |
|---|---|
| Postgres and Redis containers | Running (up 2 days, healthy). Redis is started but nothing in the code needs it. |
| Backend on 8000, frontend on 3100 | **Not running** |
| Database | 499 MB. 13,992 orders listed, 2,209 with text, 72,970 chunks of which 65,974 embedded (6,996 from newly fetched orders are not), 502 machine-labelled orders (0 human-checked), 1 user, 2 cases (1 demo), 1 completed hearing run |
| Order download (1,000 requested) | Stopped at about 190 |
| Tools | Python 3.12.16 in `backend/.venv`, Node 24.21, Docker; 743 GB free disk |
| Tests | Full backend suite passed on 11 Nov (222 tests). Not re-run in this audit. |

## 7. Findings that matter for the demo

1. **Three items on the requested journey do not exist in this design.** Uploaded buyer documents
   are not chunked or embedded and there is no "ask a question about my document" feature: the
   app extracts structured facts (each with its source page) instead. Chunks, embeddings and
   vector search exist for the public orders only.
2. **The trained classifiers are not connected to the app.** They run from the command line. The
   hearing report shows outcome shares counted from retrieved precedents, not a classifier output.
3. **Precedent search has no page of its own.** It runs inside the hearing.
4. **The hearing and fact extraction depend on the free Gemini tier**, which often answers 429 /
   503. A hearing can take several minutes or fail. One completed run is stored.
5. **The privacy rule limits the live demo to a fictional case.** Only cases marked as demo may be
   sent to Gemini; the API must be started with `-AllowDemo`.
6. **Email is not sent.** Sign-up needs the verification link from `data/outbox/`.
7. **6,996 chunks have no embedding**, so the newest orders are found by keyword search only
   until `scripts.embed_chunks` is run.
8. **Model accuracy is modest** (MODEL_EVALUATION.md, MODEL_TRAINING_GUIDE.md): citation checker
   precision 100% / recall 98.3%; outcome prediction best 72.9%; claim type 74.3%. Labels are
   machine-made and unchecked. These numbers must be presented as they are.

## Update 13 Nov 2026

Added after the audit, each tested live (`scripts.e2e_check insights`, 16 of 16 checks) and by unit
tests (`backend/tests/test_insights.py`):

| Addition | Where | Notes |
|---|---|---|
| Complaint draft | `GET /api/v1/cases/{id}/draft`, step 7 of a case | Assembled by code from the buyer's facts and from citations verified in the latest hearing. No model call; unknown items are left as bracketed blanks and listed. Download as .txt. |
| Rule-based outcome estimate | `GET /api/v1/cases/{id}/estimate`, shown on the report | Counts how past orders with the same claim type and delay ended; states its measured accuracy (72.9%). |
| Search over past orders | `GET /api/v1/search/orders`, page `/search` | Hybrid keyword + vector search over the public orders, with order, page and passage. |
| Classifier demo | `POST /api/v1/predictions/order-text`, on `/search` | The trained claim-type and outcome models on pasted order text, each answer shown with its measured test accuracy. |
| Google sign-in | configured locally | A real Google sign-in completed on 13 Nov (seen in the API log). |
| Embeddings | `scripts.embed_chunks` | The 6,996 chunks without an embedding are being embedded. |

Still not present: question-answering over an uploaded document, embeddings of uploaded
documents, a public deployment. Accuracy figures are unchanged.
