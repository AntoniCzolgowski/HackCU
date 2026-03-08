$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $RepoRoot "apps\api"

Push-Location $RepoRoot
try {
    python -m pip install -r (Join-Path $RepoRoot "apps\api\requirements.txt")
    Push-Location $ApiDir
    try {
        python -m app.data_refresh
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}
