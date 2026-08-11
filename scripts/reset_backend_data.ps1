$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $root "data\runtime"
$databasePath = Join-Path $runtimeDir "codecoach.db"
$legacyDatabasePaths = @(
  (Join-Path $root "apps\codecoach.db"),
  (Join-Path $root "apps\backend\codecoach.db")
)

if (-not (Test-Path -LiteralPath $runtimeDir)) {
  New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}

if (Test-Path -LiteralPath $databasePath) {
  Remove-Item -LiteralPath $databasePath
}

foreach ($legacyDatabasePath in $legacyDatabasePaths) {
  if (Test-Path -LiteralPath $legacyDatabasePath) {
    Remove-Item -LiteralPath $legacyDatabasePath
  }
}

Push-Location "$root\apps\backend"
try {
  python -c "from app.db.seed import seed_demo_data; seed_demo_data(); print('Backend demo data reset complete.')"
} finally {
  Pop-Location
}
