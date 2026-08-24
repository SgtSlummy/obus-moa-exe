[CmdletBinding()]
param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\OBus-Thor",
    [string]$LocalSttModelPath = '',
    [switch]$Start
)

$ErrorActionPreference = 'Stop'
$PackageRoot = Split-Path -Parent $PSCommandPath
$SourceExe = Join-Path $PackageRoot 'OBus.exe'
$SeedState = Join-Path $PackageRoot 'thor-loki-state.json'

if (-not (Test-Path -LiteralPath $SourceExe)) { throw "Missing OBus.exe beside $PSCommandPath" }
if (-not (Test-Path -LiteralPath $SeedState)) { throw "Missing thor-loki-state.json beside $PSCommandPath" }
if ($LocalSttModelPath -and -not (Test-Path -LiteralPath $LocalSttModelPath)) {
    throw "LocalSttModelPath does not exist: $LocalSttModelPath"
}

$StateRoot = Join-Path $InstallRoot 'state'
New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
Copy-Item -LiteralPath $SourceExe -Destination (Join-Path $InstallRoot 'OBus.exe') -Force
Copy-Item -LiteralPath $SeedState -Destination (Join-Path $StateRoot 'obus_state.json') -Force
Copy-Item -LiteralPath (Join-Path $PackageRoot 'Start-OBus-Thor.cmd') -Destination (Join-Path $InstallRoot 'Start-OBus-Thor.cmd') -Force
Copy-Item -LiteralPath (Join-Path $PackageRoot 'Test-Loki-Route.ps1') -Destination (Join-Path $InstallRoot 'Test-Loki-Route.ps1') -Force

if ($LocalSttModelPath) {
    $resolvedVoicePath = [System.IO.Path]::GetFullPath($LocalSttModelPath)
    Set-Content -LiteralPath (Join-Path $InstallRoot 'voice-model-path.txt') -Value $resolvedVoicePath -NoNewline
}

Write-Host 'OBus installed for Thor primary mode.' -ForegroundColor Green
Write-Host 'Loki worker target: 100.73.36.108 (Tailscale SSH guide only).' -ForegroundColor Cyan
Write-Host "Text launch: $(Join-Path $InstallRoot 'Start-OBus-Thor.cmd')"
Write-Host "Route check: powershell -ExecutionPolicy Bypass -File $(Join-Path $InstallRoot 'Test-Loki-Route.ps1')"
Write-Host 'Remote terminal remains disabled until its Thor-side account and identity-file reference are explicitly configured.' -ForegroundColor Yellow

if ($Start) { Start-Process -FilePath (Join-Path $InstallRoot 'Start-OBus-Thor.cmd') }
