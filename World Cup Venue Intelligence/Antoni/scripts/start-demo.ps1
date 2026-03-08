$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $RepoRoot "apps\api"
$PidFile = Join-Path $PSScriptRoot ".demo-pids.json"
$LogDir = Join-Path $PSScriptRoot ".demo-logs"

function Wait-ForHttp {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing | Out-Null
            return
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }

    throw "Timed out waiting for $Url"
}

& (Join-Path $PSScriptRoot "stop-demo.ps1")

Push-Location $RepoRoot
try {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

    if (-not (Test-Path (Join-Path $RepoRoot "node_modules"))) {
        npm install
    }

    python -m pip install -r (Join-Path $RepoRoot "apps\api\requirements.txt")

    Push-Location $ApiDir
    try {
        python -m app.generate_assets
    }
    finally {
        Pop-Location
    }

    $backendCommand = "Set-Location '$ApiDir'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    $frontendCommand = "Set-Location '$RepoRoot'; npm run web:dev"
    $backendOut = Join-Path $LogDir "backend.out.log"
    $backendErr = Join-Path $LogDir "backend.err.log"
    $frontendOut = Join-Path $LogDir "frontend.out.log"
    $frontendErr = Join-Path $LogDir "frontend.err.log"

    foreach ($logFile in @($backendOut, $backendErr, $frontendOut, $frontendErr)) {
        if (Test-Path $logFile) {
            Remove-Item $logFile -Force
        }
    }

    $backend = Start-Process powershell -ArgumentList @("-NoLogo", "-NoProfile", "-Command", $backendCommand) -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru
    $frontend = Start-Process powershell -ArgumentList @("-NoLogo", "-NoProfile", "-Command", $frontendCommand) -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru

    @{
        backend_pid = $backend.Id
        frontend_pid = $frontend.Id
        backend_out = $backendOut
        backend_err = $backendErr
        frontend_out = $frontendOut
        frontend_err = $frontendErr
    } | ConvertTo-Json | Set-Content -Encoding UTF8 $PidFile

    try {
        Wait-ForHttp "http://127.0.0.1:8000/api/health"
        Wait-ForHttp "http://127.0.0.1:8000/api/matches"
        Wait-ForHttp "http://127.0.0.1:5173"
    }
    catch {
        Write-Host "Demo startup failed. Recent backend stderr:" -ForegroundColor Red
        if (Test-Path $backendErr) {
            Get-Content $backendErr -Tail 40
        }
        Write-Host "Recent backend stdout:" -ForegroundColor Yellow
        if (Test-Path $backendOut) {
            Get-Content $backendOut -Tail 40
        }
        Write-Host "Recent frontend stderr:" -ForegroundColor Red
        if (Test-Path $frontendErr) {
            Get-Content $frontendErr -Tail 40
        }
        Write-Host "Recent frontend stdout:" -ForegroundColor Yellow
        if (Test-Path $frontendOut) {
            Get-Content $frontendOut -Tail 40
        }
        throw
    }

    Write-Host "Backend log: $backendOut"
    Write-Host "Frontend log: $frontendOut"
    Start-Process "http://127.0.0.1:5173"
}
finally {
    Pop-Location
}
