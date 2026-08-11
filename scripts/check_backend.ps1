$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\apps\backend"
try {
  python -m compileall app
  python -m pytest tests
} finally {
  Pop-Location
}
