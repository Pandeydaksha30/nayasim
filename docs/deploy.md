# Deploying NyayaSim

This setup runs the whole app (database, API, website) on one Linux server with Docker. It is meant for
a **private demo**: there are no user accounts yet, so the public HTTPS setup puts the whole site behind
one shared password.

## What runs

| Service    | Image                              | Purpose                                                      |
|------------|------------------------------------|--------------------------------------------------------------|
| `postgres` | `pgvector/pgvector:0.8.0-pg17`     | Database with vector search. Data in the `pgdata` volume.    |
| `migrate`  | `nyayasim-api` (built from `backend/`) | Runs `alembic upgrade head` once, then exits.            |
| `api`      | `nyayasim-api`                     | FastAPI on port 8000; includes Tesseract OCR (English + Hindi). Uploads in the `appdata` volume. |
| `web`      | `nyayasim-web` (built from `frontend/`) | Next.js website on port 3000.                           |
| `caddy`    | `caddy:2.10-alpine` (profile `https`) | HTTPS certificates, site password, one address for site + API. |

## 1. Local test on your own machine

```bash
cp infra/.env.prod.example infra/.env.prod
```

Edit `infra/.env.prod`: set `POSTGRES_PASSWORD`, and `GEMINI_API_KEY` if you want hearings to run.
Leave the URLs as `http://localhost:3000` and `http://localhost:8000`.

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build
```

Open http://localhost:3000. Check the API with `curl http://localhost:8000/health`.

The new database is empty. The example case works straight away; precedent search and hearings need
orders loaded (see `docs/ingestion.md`). To copy your local database across:

```bash
docker exec contractiq-postgres pg_dump -U contractiq -Fc contractiq > nyayasim.dump
docker cp nyayasim.dump nyayasim-postgres-1:/tmp/
docker exec nyayasim-postgres-1 pg_restore -U nyayasim -d nyayasim --clean --if-exists --no-owner /tmp/nyayasim.dump
```

(Adjust the container and user names to match `docker ps` and your local `.env`.)

## 2. Public demo with HTTPS

Needs a Linux server with Docker, ports 80 and 443 open, and a domain whose DNS A record points at it.

1. In `infra/.env.prod` set:
   - `DOMAIN=demo.example.com`
   - `PUBLIC_WEB_URL=https://demo.example.com` and `PUBLIC_API_URL=https://demo.example.com` (the same
     address: Caddy sends `/api/*` and `/health` to the API and everything else to the website).
   - `BASIC_AUTH_HASH` from:
     ```bash
     docker run --rm caddy:2.10-alpine caddy hash-password --plaintext 'choose-a-password'
     ```
     In `.env.prod`, write every `$` in the hash as `$$` so Docker Compose does not read it as a variable.
2. Start:
   ```bash
   docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod --profile https up -d --build
   ```
3. Open https://demo.example.com and sign in with `BASIC_AUTH_USER` and the password.

Ports 3000 and 8000 stay bound to `127.0.0.1`, so the only way in from outside is through Caddy.

## Before showing it to real buyers

- `NYAYASIM_PRIVATE_LLM_OK` must stay `false` until a model that keeps no data is configured. With it
  off, real documents are stored and read with OCR, but never sent to the AI model.
- Rotate the Gemini key that was shared in chat, and put the new one only in `.env.prod`.
- The backtest (`docs/backtest.md`) and the 200-record hand check must be finished before any accuracy
  is claimed.
- Back up the `pgdata` and `appdata` volumes (e.g. a nightly `pg_dump`).

## Updating

```bash
git pull
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod --profile https up -d --build
```

`migrate` runs again on every start and applies any new migrations before the API starts.
