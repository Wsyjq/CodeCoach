$ErrorActionPreference = "Stop"
$env:CODECOACH_AUTH_REQUIRED = "true"
$env:CODECOACH_USE_LLM = "false"
$frontendPort = if ($env:E2E_FRONTEND_PORT) { $env:E2E_FRONTEND_PORT } else { "18101" }
$env:CODECOACH_CORS_ORIGINS = "http://127.0.0.1:$frontendPort,http://localhost:$frontendPort"
$port = if ($env:E2E_BACKEND_PORT) { $env:E2E_BACKEND_PORT } else { "18100" }
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath "$root\apps\backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port $port
