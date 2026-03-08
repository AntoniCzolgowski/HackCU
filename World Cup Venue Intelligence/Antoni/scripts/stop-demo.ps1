$ErrorActionPreference = "SilentlyContinue"

$PidFile = Join-Path $PSScriptRoot ".demo-pids.json"

function Stop-PortListeners {
    param(
        [int[]]$Ports
    )

    foreach ($port in $Ports) {
        $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($connection in $connections) {
            if ($connection.OwningProcess) {
                Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

if (Test-Path $PidFile) {
    $pids = Get-Content $PidFile | ConvertFrom-Json
    foreach ($property in $pids.PSObject.Properties) {
        if ($property.Value) {
            Stop-Process -Id $property.Value -Force -ErrorAction SilentlyContinue
        }
    }

    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

Stop-PortListeners -Ports @(8000, 5173, 5177)
