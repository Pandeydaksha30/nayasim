# Start the NyayaSim API for local development (PowerShell).
#   .\scripts\dev-api.ps1                # http://127.0.0.1:8000, website expected on :3100
#   .\scripts\dev-api.ps1 -Port 8010 -WebPort 3110
#   .\scripts\dev-api.ps1 -AllowDemo     # lets you mark your own test case as fictional "demo"
param([int]$Port = 8000, [int]$WebPort = 3100, [switch]$AllowDemo)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\backend")
$env:NYAYASIM_PUBLIC_URL = "http://localhost:$WebPort"
$env:NYAYASIM_ALLOW_DEMO_CASES = if ($AllowDemo) { "true" } else { "false" }
$env:NYAYASIM_CORS_ORIGINS = "http://localhost:$WebPort,http://127.0.0.1:$WebPort"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $Port --proxy-headers
