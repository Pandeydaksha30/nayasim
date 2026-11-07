# NyayaSim

Before a homebuyer files against a builder, NyayaSim shows how a RERA hearing on their
facts is likely to go, what they could get, and where their case is weak — citing real
past orders. Built on the ContractIQ base (old code kept in `legacy/contractiq/`).

**Status (7 Nov 2026):** frontend on demo data; Python interest/refund calculator live and
tested; data gate passed for Haryana (see `docs/data-gate-2026-11-07.md`). Order store,
retrieval, agents and backtest are not built yet.

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

Tests: `cd backend; .\.venv\Scripts\python.exe -m pytest`

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
| `backend/tests/` | Unit tests (hand-worked figures) and API tests. |
| `backend/scripts/data_gate_haryana.py` | Reproducible data-availability check for HRERA Gurugram. |
| `frontend/app/` | Next.js pages: cases, upload, facts, questions, money, hearing, report, draft. |
| `frontend/lib/api.ts` | API client; throws on failure, never substitutes numbers. |
| `frontend/lib/demo-case.ts` | Fictional demo case. Every order reference is marked `DEMO`. |
| `infra/docker-compose.yml` | Postgres + pgvector and Redis for the order store (from step 3). |
| `docs/` | Decisions and results (data gate). |
| `legacy/contractiq/` | Original ContractIQ RAG backend, kept for reference. |

## Ground rules

1. No fabricated orders, citations, facts or outcomes.
2. Money is computed by deterministic Python, never by an LLM.
3. Every extracted fact keeps its document and page.
4. Every citation must be verifiable against a stored order.
5. Errors are shown, not hidden.
