# NyayaSim

Before a homebuyer files against a builder, NyayaSim shows how a RERA hearing on their
facts is likely to go, what they could get, and where their case is weak — citing real
past orders. Built on the ContractIQ base (old code kept in `legacy/contractiq/`).

**Status (7 Nov 2026):** frontend on demo data; Python interest/refund calculator live and
tested; data gate passed for Haryana (see `docs/data-gate-2026-11-07.md`); order-store and
case database schema in place and tested. Ingestion, retrieval, agents and backtest are not
built yet.

## Database

Postgres 17 + pgvector and Redis run in Docker (start Docker Desktop first):

```powershell
docker compose -f infra/docker-compose.yml up -d
cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head
```

Check the connection: `cd backend; .\.venv\Scripts\python.exe -m scripts.check_db`.
Use `127.0.0.1`, not `localhost`, in `NYAYASIM_DATABASE_URL` on Windows: `localhost` tries
IPv6 first and Docker Desktop leaves that connection hanging.

Tables (schema in `backend/migrations/versions/0001_order_store.py`):

| Table | Holds | Rule the database enforces |
|---|---|---|
| `fetch_log` | every download attempt | status or error must be recorded |
| `orders` | one regulator decision | unique per source + complaint + date; fetched ⇒ hash stored |
| `order_pages` | text of each page | OCR pages must name the OCR engine |
| `order_chunks` | retrieval passages + embedding + full-text index | offsets must match the text exactly; page must exist |
| `case_records` | structured outcome of an order | fixed outcome/claim vocabularies; per-field sources |
| `cases`, `case_documents` | a buyer's case and uploads | page count > 0, no duplicate file |
| `facts` | facts read from buyer documents | document, existing page and character span required |

## Run locally

Needs Node 20+ and Python 3.12 via [uv](https://docs.astral.sh/uv/) (`pip install uv`).

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm ci
npm run dev
```

On Windows PowerShell 5.1 (no `&&`; run each in its own terminal tab), after `uv sync` once:

```powershell
cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

```powershell
cd frontend; npm run dev
```

Tests: `cd backend; .\.venv\Scripts\python.exe -m pytest` (database tests need Docker running;
they are skipped with a printed reason otherwise, or fail if `NYAYASIM_REQUIRE_DB=1`).

If the frontend shows "Cannot find module './NNN.js'", a dev server was running while plain
`npm run build` rewrote `.next`. Stop the dev server, delete `frontend\.next`, start again.

Open http://localhost:3100. The frontend calls the API at `NEXT_PUBLIC_API_URL`
(default `http://localhost:8000`); see `frontend/.env.example`. If the API is down, pages
that show money say so — they never fall back to a figure computed elsewhere.

## Test

```bash
cd backend
uv run pytest
uv run ruff check .
```

```bash
cd frontend
npx tsc --noEmit
npm run build:check   # builds into .next-check; safe while npm run dev is running
```

## Layout

| Path | What it is |
|---|---|
| `backend/app/calculator/interest.py` | Delay-interest and refund maths. Decimal, per payment, no LLM. |
| `backend/app/api/calculations.py` | `POST /api/v1/calculations/interest`: validates input, returns money as strings. |
| `backend/app/main.py`, `config.py` | FastAPI app, CORS limited to configured origins. |
| `backend/app/db/models.py` | SQLAlchemy mappings of the database tables. |
| `backend/migrations/` | Alembic migrations (schema as plain SQL). |
| `backend/tests/` | Calculator, API and database-constraint tests. |
| `backend/scripts/data_gate_haryana.py` | Reproducible data-availability check for HRERA Gurugram. |
| `backend/scripts/check_db.py` | Connection check with timings per address. |
| `frontend/app/` | Next.js pages: cases, upload, facts, questions, money, hearing, report, draft. |
| `frontend/lib/api.ts` | API client; throws on failure, never substitutes numbers. |
| `frontend/lib/demo-case.ts` | Fictional demo case. Every order reference is marked `DEMO`. |
| `infra/docker-compose.yml` | Postgres 17 + pgvector 0.8 and Redis, bound to 127.0.0.1 only. |
| `docs/` | Decisions and results (data gate). |
| `legacy/contractiq/` | Original ContractIQ RAG backend, kept for reference. |

## Ground rules

1. No fabricated orders, citations, facts or outcomes.
2. Money is computed by deterministic Python, never by an LLM.
3. Every extracted fact keeps its document and page.
4. Every citation must be verifiable against a stored order.
5. Errors are shown, not hidden.
