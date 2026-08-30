param(
    [string]$HostUrl = "http://100.73.36.108:8000",
    [string]$DesktopPath = [Environment]::GetFolderPath("Desktop")
)

$ErrorActionPreference = "Stop"
$target = Join-Path $DesktopPath "OBus Thor Voice Mic.cmd"
$launcher = @"
@echo off
start "" "$HostUrl/voice-link"
"@
Set-Content -LiteralPath $target -Value $launcher -Encoding ASCII
Write-Host "Installed OBus Thor Voice Mic on: $target"
