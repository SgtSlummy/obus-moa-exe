param([switch]$Foreground)
$ErrorActionPreference = 'Stop'
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { throw 'OBus project path unavailable.' }
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
$BridgeScript = Join-Path $ProjectRoot 'obus_hermes_bridge.py'
$HealthUrl = 'http://127.0.0.1:38174/health'
$env:OBUS_URL = 'http://127.0.0.1:38173'
$env:OBUS_HOST = '127.0.0.1'
$env:OBUS_PORT = '38173'
$env:OBUS_BRIDGE_HOST = '127.0.0.1'
$env:OBUS_BRIDGE_PORT = '38174'
$env:OBUS_MODEL = 'gpt-oss:20b'
$env:OBUS_ALLOW_LOCAL_CLIENTS = '1'
$env:OCCULTBUS_HOME = Join-Path $env:LOCALAPPDATA 'OBus'

try {
    $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3
    if ($health.status -eq 'ok') { exit 0 }
} catch { }

if ($Foreground) {
    & $Python $BridgeScript
    exit $LASTEXITCODE
}
Start-Process -FilePath $Python -ArgumentList @('"' + $BridgeScript + '"') -WorkingDirectory $ProjectRoot -WindowStyle Hidden
