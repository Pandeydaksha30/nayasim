# Deploying NyayaSim

The whole app (database, API, website, HTTPS) runs on one Linux server with Docker. Users sign
up with their own accounts (docs/accounts.md); optionally the whole site can also sit behind one
shared password for a private demo.

## What runs

| Service    | Image                              | Purpose |
|------------|------------------------------------|---------|
| `postgres` | `pgvector/pgvector:0.8.0-pg17`     | Database with vector search. Data in the `pgdata` volume. |
| `migrate`  | `nyayasim-api` (from `backend/`)   | Runs `alembic upgrade head` once, then exits. |
| `api`      | `nyayasim-api`                     | FastAPI on 8000, Tesseract OCR (English + Hindi). Uploads, email outbox, model cache in the `appdata` volume. |
| `web`      | `nyayasim-web` (from `frontend/`)  | Next.js on 3000; forwards `/api` to the API when Caddy is not used. |
| `caddy`    | `caddy:2.10-alpine` (profile `https`) | HTTPS certificates (automatic, free), one address for site + API. |

## Where to host it (free)

The API needs about 2 GB of memory (OCR + search model) and the database is ~0.5 GB with all
current orders. **Oracle Cloud "Always Free"** fits: an Ampere A1 VM with up to 4 CPUs / 24 GB,
Mumbai or Hyderabad region. A free name from **duckdns.org** gives you a domain. Small free tiers
(Render, Railway, 1 GB VMs) are too small.

1. Create the VM (Ubuntu 24.04, Ampere A1, 2–4 CPUs, 12–24 GB). Open TCP 80 and 443 in the VCN
   security list **and** on the VM (`sudo iptables -I INPUT -p tcp -m multiport --dports 80,443 -j ACCEPT`
   then `sudo netfilter-persistent save`; Oracle's Ubuntu image blocks them by default).
2. Point the DuckDNS name at the VM's public IP.
3. Copy the project and the data file to the VM (`scp nyayasim.zip nyayasim-data.dump ubuntu@IP:`),
   unzip, `cd nyayasim`.

## One-command deploy

```bash
DOMAIN=nyayasim.duckdns.org DATA=~/nyayasim-data.dump bash infra/deploy.sh
```

It installs Docker if needed, writes `infra/.env.prod` (random database password, HTTPS cookie
settings), builds, starts, loads the order data (about 2 minutes) and checks
`https://DOMAIN/health`. Then open `https://DOMAIN/signup`.

Add these before running (or edit `infra/.env.prod` afterwards and run the script again):

| Setting | Why | How |
|---|---|---|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | **Needed for a public site:** new users must receive the confirmation email | docs/accounts.md → Setting up email |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | "Continue with Google" | docs/accounts.md → Setting up Google sign-in; redirect URI `https://DOMAIN/api/v1/auth/google/callback` |
| `GEMINI_API_KEY` | AI fact extraction and hearings for demo cases | Use a **new** key (the old one was shared in chat) |
| `SITE_PASSWORD` | Optional: one extra shared password in front of everything | Sets `CADDYFILE=Caddyfile.locked` |

Without SMTP the emails stay inside the server:
`docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod exec api ls /srv/data/outbox`.

## The order data

A new database has no orders, so search and hearings find nothing. The data file holds the public
orders only: `orders`, `order_pages`, `order_chunks` (with embeddings), `case_records`, `fetch_log`.
It contains **no** user, case or document tables.

```bash
bash infra/export-data.sh                       # on the dev PC -> release/nyayasim-data.dump (168 MB)
bash infra/import-data.sh nyayasim-data.dump    # on the server, stack running; refuses if orders exist
FORCE=1 bash infra/import-data.sh new.dump      # replace the order data
```

The file is over GitHub's 100 MB limit for repository files: attach it to a GitHub Release
(2 GB limit) or copy it with `scp`.

## Local test of the production stack

```bash
DOMAIN=none WEB_PORT=3000 bash infra/deploy.sh
```

Starts on `http://SERVER_IP:3000` without HTTPS (the website forwards `/api` itself). Only for a
machine behind a firewall.

Tested 9 Nov 2026 on Docker Desktop (Windows) with a clean project copy: build, migrations, data
import (13,992 orders / 65,974 chunks in 1 min 58 s), hybrid search inside the container, and
sign-up → confirm → sign-in → create case through the website's `/api` forwarding.

## Before showing it to real buyers

- `NYAYASIM_PRIVATE_LLM_OK` must stay `false` until a model that keeps no data is configured.
- Configure SMTP; publish the Google consent screen.
- Have a lawyer review `/terms` and `/privacy` (marked as drafts) and publish a grievance contact.
- Finish the backtest and the 200-record hand check before claiming any accuracy.
- Back up the `pgdata` and `appdata` volumes (e.g. nightly `pg_dump`).

## Updating

```bash
git pull     # or copy the new files over
bash infra/deploy.sh
```

`migrate` runs on every start and applies new migrations before the API starts.
