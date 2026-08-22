$ErrorActionPreference = 'Stop'
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { throw 'OBus project path unavailable.' }
$Python = 'C:\Users\Hermes\warden-discord-bot\.venv\Scripts\python.exe'
$BridgeScript = Join-Path $ProjectRoot 'obus_hermes_bridge.py'
$HealthUrl = 'http://127.0.0.1:38174/health'

try {
    $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3
    if ($health.status -eq 'ok') { exit 0 }
} catch { }

Start-Process -FilePath $Python -ArgumentList @($BridgeScript) -WorkingDirectory $ProjectRoot -WindowStyle Hidden
