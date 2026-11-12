# Run NyayaSim locally (Windows, PowerShell)

Verified on 12 Nov 2026 on this machine. Project folder:
`C:\Users\pande\Downloads\CONTRACT_IQ\contractiq`

## Before you start

- Docker Desktop is running.
- `backend\.env` exists and contains `GEMINI_API_KEY=...` (never commit or show this file).
- First time only: `backend\.venv` and `frontend\node_modules` already exist on this machine.

## Start (three PowerShell windows)

**1. Database** (PostgreSQL 17 + pgvector):

```powershell
docker compose -f C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\infra\docker-compose.yml up -d
```

**2. Backend** (FastAPI on port 8000; `-AllowDemo` lets fictional demo cases use the model):

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\scripts\dev-api.ps1 -AllowDemo
```

**3. Website** (Next.js on port 3100):

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\scripts\dev-web.ps1
```

Leave windows 2 and 3 open. Stop either with Ctrl+C.

## Addresses

| What | Address |
|---|---|
| Website | http://localhost:3100 |
| API documentation (Swagger) | http://localhost:8000/docs |
| API health | http://localhost:8000/health (also http://localhost:3100/health through the site) |
| Database | 127.0.0.1:5432, database `nyayasim` (inside Docker container `infra-postgres-1`) |

## Check that everything works

```powershell
cd C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\backend
.\.venv\Scripts\python.exe -m scripts.e2e_check setup
.\.venv\Scripts\python.exe -m scripts.e2e_check facts
.\.venv\Scripts\python.exe -m scripts.e2e_check hearing
.\.venv\Scripts\python.exe -m scripts.e2e_check session
```

Each line printed is PASS or FAIL. `facts` and `hearing` call Gemini and can be slow or fail when
the free tier is busy; the other two do not need it. Every `setup` run adds one more demo case and
one private test case to the demo user.

Unit tests (224, about 2 minutes):

```powershell
cd C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\backend
$env:NYAYASIM_REQUIRE_DB = "1"; .\.venv\Scripts\python.exe -m pytest -q
```

## Demo user

Created by `scripts.e2e_check setup`. Email and password are in
`C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\data\demo-credentials.txt` (git-ignored).

## Signing up a new user by hand

No email provider is configured, so the confirmation email is written to a file instead of being
sent. After signing up, open the newest file in `data\outbox\` and open the link inside it:

```powershell
Get-ChildItem C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\data\outbox | Sort-Object LastWriteTime | Select-Object -Last 1 | Get-Content
```

## Sample fictional documents

`demo\sample-documents\`: `agreement.pdf`, `receipts.pdf`, `builder_letter.pdf`,
`receipt_scan.png` (an image, read by OCR). Every name and number in them is invented.

## Common problems

| Symptom | Cause and fix |
|---|---|
| Website shows "refused to connect" | Window 3 is not running. Start it again. |
| Pages load but nothing saves, or login fails with a server error | Window 2 (backend) is not running, or Docker is stopped. |
| "Demo cases cannot be created on this server" when creating a demo case | The backend was started without `-AllowDemo`. |
| Hearing or fact extraction fails with a "busy" or 429 / 503 message | Gemini free tier is overloaded. Wait a minute and retry, or show the stored hearing (DEMO_GUIDE.md). |
| Port already in use | An old server is still running. Close its window, or use `-Port 8010` (API) and `-Port 3110 -ApiPort 8010` (web), and start the API with `-WebPort 3110`. |

## Backup and restore

A database backup made before the demo work: `data\backups\pre-demo-2026-11-12.dump`.
Git checkpoint: branch `backup/pre-demo-2026-11-12` and tag `checkpoint-pre-demo`.
