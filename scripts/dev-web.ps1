# Start the NyayaSim website for local development (PowerShell).
#   .\scripts\dev-web.ps1                # http://localhost:3100, API expected on :8000
#   .\scripts\dev-web.ps1 -Port 3110 -ApiPort 8010
param([int]$Port = 3100, [int]$ApiPort = 8000)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\frontend")
$env:API_URL = "http://127.0.0.1:$ApiPort"
npx next dev -p $Port
