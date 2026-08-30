param([string]$DesktopPath = [Environment]::GetFolderPath("Desktop"))
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$launcher = "@echo off`r`npython `"$root\voice_link\relay_pad.py`"`r`n"
Set-Content -LiteralPath (Join-Path $DesktopPath "OBus Relay Pad.cmd") -Value $launcher -Encoding ASCII
Write-Host "Installed OBus Relay Pad on: $DesktopPath"
