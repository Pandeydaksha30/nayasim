# NyayaSim

Before a home buyer files a RERA complaint against a builder, NyayaSim reads their papers,
works out what they are owed, and shows how the authority decided similar cases, with every
fact tied to a page and every citation checked against the stored order.

**Status (9 Nov 2026):** working end to end for one region (HRERA Gurugram: 13,992 orders
listed, 2,019 downloaded and searchable with hybrid keyword + semantic search, 248 with extracted
outcomes). See `AGENT_STATUS.md` for what is measured and what is not. User accounts with email/password and
Google sign-in, per-user case isolation, and a tested one-command server deploy. Accuracy is
**not** claimed yet: the 200-record hand check and a clean backtest rerun are pending
(see `HANDOFF.md`).

| Feature | Where |
|---|---|
| Accounts: sign-up, email confirmation, sign-in, Google sign-in, password reset, account deletion | `backend/app/auth/`, `backend/app/api/auth.py`, `frontend/app/{login,signup,account,...}`; see [docs/accounts.md](docs/accounts.md) |
| Buyer documents → verified facts (each with page + quote) | [docs/buyer-documents.md](docs/buyer-documents.md) |
| Delay interest / refund calculator (deterministic Python) | `backend/app/calculator/` |
| Order ingestion + OCR (English, Hindi) | [docs/ingestion.md](docs/ingestion.md) |
| Precedent search with a decision-date cutoff | [docs/search.md](docs/search.md) |
| Citation checker | [docs/citations.md](docs/citations.md) |
| Simulated hearing + decision report | [docs/hearing.md](docs/hearing.md) |
| Time-split backtest | [docs/backtest.md](docs/backtest.md) |
| Production deploy (Docker, HTTPS, data import) | [docs/deploy.md](docs/deploy.md) |

## Run it locally (Windows)

Needs: Docker Desktop, Python 3.12 with [uv](https://docs.astral.sh/uv/) (`pip install uv`), Node 20+.

**First time only**

```powershell
docker compose -f infra/docker-compose.yml up -d
cd backend; uv sync; copy .env.example .env; cd ..
cd frontend; npm ci; cd ..
```

Put `GEMINI_API_KEY=...` in `backend\.env` if you want AI fact extraction and hearings on demo cases.

**Every time**, in two terminal windows from the repo folder:

```powershell
.\scripts\dev-api.ps1        # API on http://127.0.0.1:8000 (applies migrations first)
```

```powershell
.\scripts\dev-web.ps1        # website on http://localhost:3100
```

Open http://localhost:3100 and click **Create account**. Without an email server configured,
the confirmation email is saved to `data\outbox\` and its link is printed in the API window;
open that link to confirm. Set `NYAYASIM_SMTP_*` in `backend\.env` to send real email, and
`NYAYASIM_GOOGLE_CLIENT_ID` / `_SECRET` to show "Continue with Google" (docs/accounts.md).

Ports taken? `.\scripts\dev-api.ps1 -Port 8010 -WebPort 3110` and
`.\scripts\dev-web.ps1 -Port 3110 -ApiPort 8010`.

Search data: a fresh database has no orders, so search and hearings find nothing until orders
are loaded, by running ingestion (docs/ingestion.md) or importing the data file (docs/deploy.md).

## Deploy

```bash
DOMAIN=your.domain DATA=nyayasim-data.dump bash infra/deploy.sh
```

Full guide, including free hosting, Google sign-in and email: [docs/deploy.md](docs/deploy.md).

## Test

```powershell
cd backend; uv run pytest; uv run ruff check .      # database tests need Docker running
cd frontend; npx tsc --noEmit; npm run build:check
```

## Layout

| Path | What it is |
|---|---|
| `backend/app/api/` | HTTP routes: auth, cases, hearing, calculations. |
| `backend/app/auth/` | Password hashing, sessions, Google sign-in, email, rate limits. |
| `backend/app/middleware.py` | CSRF origin check and security headers. |
| `backend/app/buyer/`, `extraction/`, `ingestion/`, `retrieval/`, `verifier/`, `hearing/`, `backtest/` | The pipeline stages. |
| `backend/migrations/` | Alembic migrations (schema as plain SQL). |
| `backend/tests/` | Unit, API and database tests. |
| `frontend/app/` | Next.js pages: landing, sign-in, dashboard, case workspace, account, legal. |
| `frontend/middleware.ts` | Sends signed-out visitors from private pages to sign-in. |
| `frontend/next.config.ts` | `/api` forwarding to the backend, Content Security Policy. |
| `infra/` | Dev database compose, production compose, Caddy, deploy/export/import scripts. |
| `scripts/dev-*.ps1` | Start the API / website locally on Windows. |
| `docs/` | One document per feature, with decisions and measured results. |
| `legacy/contractiq/` | Original ContractIQ code, kept for reference. |

## Ground rules

1. No fabricated orders, citations, facts or outcomes.
2. Money is computed by deterministic Python, never by an LLM.
3. Every extracted fact keeps its document and page.
4. Every citation must be verifiable against a stored order.
5. Errors are shown, not hidden.
6. Real buyers' documents never go to an AI service that keeps data.
