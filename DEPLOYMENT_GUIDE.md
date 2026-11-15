# NyayaSim deployment guide

Release `v1.0.0-rc1`. What was verified for this release is in `RELEASE_STATUS.md`.

The whole application runs on one machine with Docker: database, API, website and (optionally)
HTTPS. Nothing outside Docker is needed on the server.

## 1. What is in the package

| Path | What |
|---|---|
| `backend/` | API source (FastAPI, Python 3.12), migrations, tests, `Dockerfile`, `pyproject.toml`, `uv.lock` |
| `frontend/` | Website source (Next.js 15), `Dockerfile`, `package.json`, `package-lock.json`, `public/` |
| `infra/` | `docker-compose.prod.yml`, `Caddyfile`, `deploy.sh`, `import-data.sh`, `export-data.sh`, `backup.sh`, `restore.sh`, `.env.prod.example` |
| `release/nyayasim-public-orders.dump` | Public HRERA Gurugram orders with page text, search passages and embeddings. No user data. |
| `data/models/*.joblib` | The two trained classifier files (used only by the classifier demo) |
| `demo/sample-documents/` | Fictional sample documents |
| `.env.example`, `backend/.env.example`, `frontend/.env.example`, `infra/.env.prod.example` | Templates with placeholders only |

Not in the package, by design: any `.env` file, keys, uploaded documents, virtual environments,
`node_modules`, build output. The embedding model for search (`BAAI/bge-small-en-v1.5`, about
67 MB) is downloaded by the API on first use and cached in its data volume; until then, and
whenever the download fails, search uses keywords only.

## 2. Requirements

- Docker with the Compose plugin (Docker Desktop on Windows or macOS, Docker Engine on Linux).
- 4 GB of memory free for Docker (the API needs about 2 GB for OCR and the search model).
- 6 GB of disk: images about 3 GB, database about 0.5 GB with the order data.
- Internet access while building, and once at first search for the embedding model.
- For a public site: a domain name pointing at the server, and ports 80 and 443 open.

## 3. Deploy on a Linux server (public site with HTTPS)

```bash
unzip NYAYASIM_FINAL_DEPLOY.zip && cd NYAYASIM_FINAL_DEPLOY
DOMAIN=your-domain.example DATA=release/nyayasim-public-orders.dump bash infra/deploy.sh
```

The script installs Docker if it is missing, writes `infra/.env.prod` with a random database
password, builds the images, starts everything, runs the migrations, loads the order data,
installs the classifier files and checks `https://DOMAIN/health`. Then open
`https://DOMAIN/signup`.

Set these in the same command, or edit `infra/.env.prod` afterwards and run the script again:

| Variable | Needed for |
|---|---|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | **Required for a public site.** Without it nobody receives the confirmation email. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | "Continue with Google". Redirect URI: `https://DOMAIN/api/v1/auth/google/callback` |
| `GEMINI_API_KEY` | Not needed on a public server: AI steps run only for demo cases, and demo cases cannot be created in production. |
| `SITE_PASSWORD` | Optional: one shared password in front of the whole site (private preview) |

## 4. Deploy on one machine without a domain (local or behind a firewall)

Works on Windows (Git Bash), macOS and Linux. On Windows extract to a short path such as
`C:\NyayaSim`.

```bash
cp infra/.env.prod.example infra/.env.prod
```

Edit `infra/.env.prod`: set `POSTGRES_PASSWORD` to a long random string. Keep
`PUBLIC_WEB_URL=http://localhost:3000` and `COOKIE_SECURE=false`. Then:

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build
```

```bash
bash infra/import-data.sh release/nyayasim-public-orders.dump
```

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod cp data/models/. api:/srv/data/models/
```

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod exec -u root api sh -c 'chown -R nyayasim:nyayasim /srv/data/models'
```

The second command matters: copied files belong to root, and the API must be able to save the
search model into the same folder. Without it search stays on keywords only.

Open `http://localhost:3000`. Without SMTP the confirmation email is written inside the API
container; read the link with:

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod exec api sh -c 'cat /srv/data/outbox/*'
```

## 5. Environment variables (`infra/.env.prod`)

| Variable | Meaning | Default |
|---|---|---|
| `POSTGRES_PASSWORD` | Database password. Required. | none |
| `PUBLIC_WEB_URL` | The address people open; also the only origin the API accepts changes from | `http://localhost:3000` |
| `COOKIE_SECURE` | `true` whenever the address is `https://`. Also switches off `/docs`. | `false` |
| `NYAYASIM_PRIVATE_LLM_OK` | **Leave `false`.** `true` would send real buyers' documents to the model. | `false` |
| `GEMINI_API_KEY` | Model key for demo cases | empty |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google sign-in | empty (button hidden) |
| `SMTP_*` | Outgoing email | empty (emails saved in the container) |
| `API_BIND`, `WEB_BIND`, `API_PORT`, `WEB_PORT` | Where the ports are published | `127.0.0.1`, 8000, 3000 |
| `DOMAIN`, `CADDYFILE`, `BASIC_AUTH_USER`, `BASIC_AUTH_HASH` | HTTPS profile | empty |

`NYAYASIM_ALLOW_DEMO_CASES` is deliberately not passed to the production stack: on a public site
anyone could tick "demo" for real documents.

## 6. Database: initialisation and migrations

There is nothing to run by hand. The `migrate` service runs `alembic upgrade head` on every start,
before the API starts; a fresh database is created empty and brought to version `0010`.

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod run --rm migrate
```

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod exec postgres psql -U nyayasim -d nyayasim -c "select version_num from alembic_version"
```

The first command applies migrations again by hand; the second shows the schema version.

## 7. Health checks

| Check | Command | Expected |
|---|---|---|
| API | `curl http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| API through the website | `curl http://localhost:3000/health` | `{"status":"ok"}` |
| Order data loaded | `curl http://localhost:3000/api/v1/stats` | `orders_read` above 0 |
| Website | `curl -I http://localhost:3000/` | `200` |
| Example case (needs no database) | open `/cases/demo/report` | the recorded report |
| Example page pictures | `curl -I http://localhost:3000/example/pages/doc-1-1.png` | `200`, `image/png` |
| Containers | `docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod ps` | `api`, `web`, `postgres` healthy; `migrate` exited 0 |
| Search uses meaning as well as keywords | sign in, search on `/search` | the result line says "Keyword and meaning-based search combined" |
| Logs | `docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod logs --tail 100 api web` | no tracebacks |

## 8. Backup and restore

```bash
bash infra/backup.sh backups
```

Writes `backups/nyayasim-db-<time>.dump` (every table) and `backups/nyayasim-files-<time>.tar.gz`
(uploaded documents, outbox, model files). They contain private documents and password hashes:
copy them off the server, keep them encrypted, delete old ones. Schedule it nightly, for example
with cron: `15 2 * * * cd /home/ubuntu/NYAYASIM_FINAL_DEPLOY && bash infra/backup.sh /var/backups/nyayasim`.

```bash
CONFIRM=yes bash infra/restore.sh backups/nyayasim-db-<time>.dump backups/nyayasim-files-<time>.tar.gz
```

Replaces the current database and files with the backup, then applies any newer migrations.

Public order data only (no user data): `bash infra/export-data.sh` and `bash infra/import-data.sh`.

## 9. Updating

Copy the new files over the old ones (keep `infra/.env.prod`), take a backup, then run
`bash infra/deploy.sh` again. Migrations are applied before the new API starts.

## 10. Stopping and removing

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod down
```

Add `-v` to also delete the database and uploaded files. That cannot be undone.

## 11. Privacy requirements and known limitations

- **AI steps are closed for real cases.** Fact extraction, cited answers, the agent and the hearing
  send text to Google Gemini, which may keep data on its free tier. They run only for cases marked
  demo, and demo cases cannot be created on a production server. A real buyer can upload, view
  the page as filed, search their own documents and public orders, use the calculator, and delete
  their data. Do not set `NYAYASIM_PRIVATE_LLM_OK=true` without a written no-retention agreement
  with the model provider.
- **No encryption at rest.** Uploaded files and page text are stored as they are in the Docker
  volumes. Use an encrypted disk on the server.
- **No automatic expiry.** Data stays until the user deletes the document, the case or the account.
- **Rate limits and background jobs live in the single API process.** Run one API container only.
  A restart fails any hearing or agent run in progress; the user can start it again.
- **No monitoring, alerting or scheduled backup is set up.** `infra/backup.sh` must be scheduled
  by you.
- **Terms and privacy pages are drafts** and have no grievance contact yet.
- **Accuracy figures are exploratory.** Outcome labels were extracted by a model and none has been
  checked by a person; the test period has been reused. The site says so wherever a figure is
  shown. See `AUDIT_2026-11-15.md` section 6 before quoting any number.
- **One authority.** Orders are from HRERA Gurugram only; 2,209 of 13,992 listed orders have text.
- The local development setup (no Docker for the app) is in `RUN_LOCAL.md`.
