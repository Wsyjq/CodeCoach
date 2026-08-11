$ErrorActionPreference = "Stop"
$backendPort = if ($env:E2E_BACKEND_PORT) { $env:E2E_BACKEND_PORT } else { "18100" }
$frontendPort = if ($env:E2E_FRONTEND_PORT) { $env:E2E_FRONTEND_PORT } else { "18101" }
$env:VITE_API_BASE_URL = "http://127.0.0.1:$backendPort"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath "$root\apps\frontend"
npm run dev -- --host 127.0.0.1 --port $frontendPort
