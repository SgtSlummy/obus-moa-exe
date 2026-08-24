[CmdletBinding()]
param(
    [string]$LokiAddress = '100.73.36.108'
)

$ErrorActionPreference = 'Stop'
Write-Host "=== Thor → Loki route check ===" -ForegroundColor Cyan
Write-Host "Target: Loki at $LokiAddress"

$tailscale = Get-Command tailscale.exe -ErrorAction SilentlyContinue
if ($tailscale) {
    & $tailscale.Source ping --timeout=5s $LokiAddress
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Tailscale ping did not succeed.' }
} else {
    Write-Warning 'tailscale.exe is not on PATH. Install/sign in to Tailscale before routing to Loki.'
}

$port = Test-NetConnection -ComputerName $LokiAddress -Port 22 -WarningAction SilentlyContinue
Write-Host ("TCP 22 reachable: {0}" -f $port.TcpTestSucceeded)
Write-Host 'This test does not open a remote shell or read identity files.' -ForegroundColor Yellow
