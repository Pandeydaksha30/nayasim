# ContractIQ deployment guide: Vercel + Render

**Status (17 Nov 2026): configuration written, not deployed.** No Vercel or Render project has
been created and nothing below has been run on those platforms yet. Docker is no longer the
deployment method (it is used only to run a local development database, see RUN_LOCAL.md).

```text
Browser ── https://<project>.vercel.app ── Next.js on Vercel (frontend/)
                │  /api/* and /health are forwarded (next.config.ts rewrites, API_URL)
                ▼
          https://<service>.onrender.com ── FastAPI on Render, native Python 3.12 (backend/)
                │                                   └─ persistent disk /var/data (uploads, model cache)
                ▼
          Render PostgreSQL 17 with pgvector
```

The browser only talks to the Vercel address. The API is reached through Vercel's rewrite, so the
session cookie belongs to the Vercel domain and no cross-site cookie settings are needed.

## What you need

- A GitHub repository with this project pushed (Vercel and Render deploy from GitHub).
- A Vercel account (Hobby is enough for the website).
- A Render account with a paid web-service plan: the persistent disk is not available on the free
  plan, and the API needs about 2 GB of memory (render.yaml uses `standard`). Check current prices.
- A Render PostgreSQL database with at least 1 GB of storage (the order data is about 0.6 GB).
- Optional: an SMTP provider (needed so new users receive the confirmation email), a Google OAuth
  client, a Gemini API key.

## 1. Push the code

```bash
git push origin nyayasim/foundation
```

Merge it into the branch Render and Vercel should deploy (for example `main`).

## 2. Database and API on Render

1. Render dashboard: **New > Blueprint**, choose the repository. Render reads `render.yaml` and
   proposes the database `contractiq-db` and the web service `contractiq-api`.
2. Fill in the variables marked "sync: false" when asked:

   | Variable | Value |
   |---|---|
   | `NYAYASIM_PUBLIC_URL` | the Vercel address, e.g. `https://contractiq.vercel.app` (you can set it after step 3 and redeploy) |
   | `NYAYASIM_CORS_ORIGINS` | the same address |
   | `GEMINI_API_KEY` | your key, or leave empty |
   | `NYAYASIM_SMTP_*` | your email provider; without it confirmation emails are only written to `/var/data/outbox` |
   | `NYAYASIM_GOOGLE_CLIENT_ID/SECRET` | optional; redirect URI `https://<vercel address>/api/v1/auth/google/callback` |

3. Apply. The build runs `pip install uv && uv sync --frozen --no-dev` (exact locked packages,
   Python from `backend/.python-version`). Every start runs `alembic upgrade head`, so the empty
   database is created up to migration 0010, including `CREATE EXTENSION vector`.
4. Check: `https://<service>.onrender.com/health` answers `{"status":"ok"}`.

If the migration fails on `CREATE EXTENSION vector`, enable the pgvector extension for the
database in the Render dashboard and redeploy.

## 3. Website on Vercel

1. Vercel dashboard: **Add New > Project**, import the repository.
2. **Root Directory: `frontend`**. Framework: Next.js (also set in `frontend/vercel.json`).
3. Environment variable (Production): `API_URL` = `https://<service>.onrender.com` (no trailing
   slash). It is read at build time by the rewrites, so redeploy after changing it.
4. Deploy, then put the Vercel address into Render's `NYAYASIM_PUBLIC_URL` and
   `NYAYASIM_CORS_ORIGINS` if not done yet, and redeploy the API.

## 4. Load the public order data

Precedent search, the hearing and the outcome estimate need the public HRERA orders
(`release/nyayasim-public-orders.dump`, 186 MB, public orders only, no user data). Use the
database's **external** connection URL from the Render dashboard:

```bash
TARGET_URL='postgresql://contractiq:...@...render.com/contractiq' bash infra/import-data.sh release/nyayasim-public-orders.dump
```

The script uses `pg_restore`/`psql` 17 if installed, otherwise runs them with Docker on your
machine. It refuses to load into a database that already has orders (`FORCE=1` replaces them).
The two trained classifier files are in the repository (`data/models/*.joblib`); nothing to copy.

## 5. Checks after deploying

| Check | Expected |
|---|---|
| `https://<vercel address>/health` | `{"status":"ok"}` (through the rewrite) |
| `https://<vercel address>/api/v1/stats` | `orders_read` above 0 after step 4 |
| Sign up, confirm the email, sign in | dashboard opens |
| Upload a text PDF, open "Ask your documents", search a passage | passages with file and page |
| Calculator page | figures appear; "Delay interest runs to" line shows the end date |
| `/search` | results; "keywords and meaning" once the embedding model has downloaded |
| Render logs | no tracebacks |

## 6. Settings that matter

| Variable (Render) | Meaning |
|---|---|
| `NYAYASIM_DATABASE_URL` | From the Render database. `postgres://` / `postgresql://` URLs are converted to the psycopg driver automatically |
| `NYAYASIM_DATA_DIR` | `/var/data`, the persistent disk: uploads, outbox, embedding-model cache |
| `NYAYASIM_COOKIE_SECURE` | `true` (HTTPS). Also hides `/docs` |
| `NYAYASIM_PRIVATE_LLM_OK` | **Keep `false`**: `true` sends real users' documents to the model |
| `NYAYASIM_ALLOW_DEMO_CASES` | Not set in production. Setting it to `true` lets any user mark a case as a fictional demo, which unlocks the AI steps for that case: use it only on a private deployment for an evaluation, never on a public site |
| `NYAYASIM_FALLBACK_MODELS`, `NYAYASIM_MODEL_RETRIES` | Gemini fallback when the main model is busy |

## 7. Differences from the Docker setup, and limitations

- **No OCR on Render.** Render's native Python runtime has no Tesseract. Text-layer PDFs work;
  scanned pages and photos are refused with a clear message. OCR still works locally.
- **Long requests through Vercel.** Fact extraction and document answers wait for the model. Vercel's
  proxy to an external address has its own time limit (check Vercel's current documentation); if
  a busy model exceeds it the browser gets an error although the API may finish. Hearings and agent
  runs are background jobs and are not affected.
- **One API instance.** Rate limits and running jobs live in memory; do not scale the service to
  more than one instance.
- **Backups.** Use Render's database backups (plan-dependent) or
  `pg_dump "<external URL>" -Fc -f contractiq.dump`. The disk holds uploaded documents: Render disk
  snapshots apply. Backups contain private documents and password hashes.
- **AI steps closed for real cases.** As before: fact extraction, answers, clause analysis, the
  agent and the hearing run only for demo cases until a no-retention model is configured.
- **Not verified on the platforms:** plan names in `render.yaml`, pgvector availability on the chosen
  database plan, memory use on Render, and the Vercel proxy limit. Check them on the first deploy.

## 8. Updating and removing

Push to the deployed branch: Render and Vercel rebuild automatically; migrations run before the new
API starts. To remove everything, delete the Vercel project, the Render web service, its disk and
the database (that deletes all users' data and cannot be undone).
