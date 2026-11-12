# Deployment checklist (draft from the audit, 12 Nov 2026)

Nothing is deployed. This lists what the code needs, which hosting fits, and what must be decided
or supplied. It will be completed in Phase 6.

## What the application needs from a host

| Need | Why |
|---|---|
| PostgreSQL 17 with the `vector` extension, about 0.5 GB now | Orders, chunks, embeddings, users, cases |
| A long-running Python process with about 2 GB of memory | Tesseract OCR and the local embedding model load inside the API; hearings run as background threads in the same process |
| Persistent disk for `data/` | Uploaded documents, email outbox, model cache |
| One public HTTPS address for site and API | The session cookie is same-origin; the site forwards `/api` to the backend |
| The order data loaded | `release/nyayasim-data.dump` (168 MB, public orders only) |

## Hosting options, checked against the code

| Option | Fit | Notes |
|---|---|---|
| **One Linux VM with Docker Compose + Caddy** (already in `infra/`) | Fits as written | `infra/deploy.sh`, `infra/docker-compose.prod.yml`, automatic HTTPS. Needs a VM with 2 GB+ memory and a domain name. Never run on a real server yet. |
| Frontend on Vercel | Compatible in principle | Standard Next.js; `API_URL` must be set at build time to the backend address. Upload size and request-time limits through Vercel's forwarding must be checked before relying on it. |
| Backend on Render | Compatible only on a paid instance | The Dockerfile works there, but the free instance (512 MB, no persistent disk, sleeps when idle) is too small for OCR + embeddings and would lose uploads. |
| Managed Postgres (Render, Neon, Supabase) | Compatible if pgvector is enabled | 0.5 GB of data must be imported with `infra/import-data.sh` or `pg_restore`; check the plan's storage limit. |
| Demo from this laptop | Fits today | Everything already runs locally; no public URL. |

Recommendation for tomorrow: make the local run the primary demo (the only path fully under our
control in one day), and attempt a public deployment only as a second step.

## Decisions and items needed from you (nothing below is done without your approval)

- [ ] Choose the host: a VM (free Oracle tier or paid), or Vercel + paid Render + managed Postgres, or local only
- [ ] Any paid resource
- [ ] A domain name or free DuckDNS name, and the DNS change
- [ ] Uploading the order data dump to the host
- [ ] Rotate the Gemini API key (it was pasted in chat twice) and set the new one on the host
- [ ] Email provider (SMTP) if real verification emails are wanted; without it, outside users cannot complete sign-up on a public host
- [ ] Google OAuth client if Google sign-in is wanted

## Configuration to set on the host (names only)

- [ ] `GEMINI_API_KEY`
- [ ] `NYAYASIM_DATABASE_URL`
- [ ] `NYAYASIM_PUBLIC_URL`, `NYAYASIM_CORS_ORIGINS` (the public site address, no wildcard)
- [ ] `COOKIE_SECURE=true`
- [ ] `NYAYASIM_PRIVATE_LLM_OK=false`
- [ ] `NYAYASIM_ALLOW_DEMO_CASES` (true only if the public demo should run hearings on fictional cases)
- [ ] `API_URL` for the frontend build
- [ ] SMTP and Google values if used

## Already in place

- [x] Health endpoint `GET /health`; Docker health checks for API and site
- [x] CORS limited to configured origins, credentials allowed, no wildcard
- [x] Secure-cookie switch, security headers, Content Security Policy
- [x] Migrations run automatically in the production stack (`migrate` service)
- [x] Persistent volumes for database and app data in the production compose file
- [x] `.env` files and `data/` git-ignored
- [x] API documentation at `/docs` on the backend

## To verify before calling it deployed

- [ ] Live URL opens over HTTPS
- [ ] Sign-up, verification and login on the live URL
- [ ] Upload and parsing on the live URL
- [ ] A hearing on a demo case completes on the live URL
- [ ] Restart the host and confirm data and uploads survive
- [ ] No secret in the repository, image or logs
