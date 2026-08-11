$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\apps\frontend"
try {
  npm run dev
} finally {
  Pop-Location
}
