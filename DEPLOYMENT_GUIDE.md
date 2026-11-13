# Deployment guide

**Status (13 Nov 2026): not deployed to any public address.** Docker images build on this machine
(`nyayasim-api`, `nyayasim-web`, rebuilt 13 Nov); the production stack has never run on a server.
Full server instructions: `docs/deploy.md`. Open items: `DEPLOYMENT_CHECKLIST.md`.

## Option A: local, without Docker for the app (what was tested)

See RUN_LOCAL.md. Database in Docker, backend and website as local processes.

## Option B: whole stack in Docker on one machine

```bash
cp infra/.env.prod.example infra/.env.prod      # then edit: passwords, GEMINI_API_KEY, domain
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build
bash infra/import-data.sh nyayasim-data.dump      # public orders + embeddings (optional, see below)
```

Services: `postgres` (pgvector, volume `pgdata`), `migrate` (runs `alembic upgrade head` to 0010,
then exits), `api` (FastAPI + Tesseract, volume `appdata` for uploads, outbox and model cache,
health check `/health`), `web` (Next.js), `caddy` (HTTPS, profile `https`).

Persistent storage: volumes `pgdata`, `appdata`, `caddydata`. Back up `pgdata` with
`infra/export-data.sh` (public data) and `pg_dump` (everything).

## Option C: public server

`docs/deploy.md`: Oracle Cloud Always Free VM (2 GB+ memory needed), DuckDNS domain, then
`DOMAIN=... DATA=... bash infra/deploy.sh`.

## Data needed for search and hearings

The precedent search and hearing need the public HRERA order data (2,209 orders, 72,970 chunks,
443 MB in Postgres). It is in `release/nyayasim-public-orders.dump` inside the project ZIP (public
regulator orders only, no user tables). Without it the app runs, but order search returns nothing
and hearings answer "no similar orders".

The embedding model (`BAAI/bge-small-en-v1.5`, ~67 MB) is downloaded automatically by fastembed on
first use into the model cache.

## Environment variables

Template: `backend/.env.example` (local) and `infra/.env.prod.example` (server). Never commit the
real files. Key settings: `DATABASE_URL`, `GEMINI_API_KEY`, `NYAYASIM_ALLOW_DEMO_CASES`,
`NYAYASIM_PRIVATE_LLM_OK` (keep `false` until a zero-retention model is configured),
`NYAYASIM_PUBLIC_URL`, `NYAYASIM_CORS_ORIGINS`.

## Before real users (not done)

Server and domain, SMTP provider, zero-retention model provider, security review, backups
schedule, monitoring, terms and privacy reviewed by a lawyer. See DEPLOYMENT_CHECKLIST.md.
