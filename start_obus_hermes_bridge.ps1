$ErrorActionPreference = 'Stop'
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { throw 'OBus project path unavailable.' }
$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
$BridgeScript = Join-Path $ProjectRoot 'obus_hermes_bridge.py'
$HealthUrl = 'http://127.0.0.1:38174/health'

try {
    $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3
    if ($health.status -eq 'ok') { exit 0 }
} catch { }

Start-Process -FilePath $Python -ArgumentList @($BridgeScript) -WorkingDirectory $ProjectRoot -WindowStyle Hidden
