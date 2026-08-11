$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\apps\backend"
try {
  uvicorn app.main:app --reload --port 8000
} finally {
  Pop-Location
}
