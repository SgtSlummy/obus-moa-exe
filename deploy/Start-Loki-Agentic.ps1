$ErrorActionPreference = 'Stop'
$config = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'thor-loki.pairing.json') | ConvertFrom-Json
$portalUri = [Uri]$config.loki.portal_url
$env:OBUS_THOR_TOKEN = $config.portal_key
$env:OBUS_HOST = $portalUri.Host
$env:OBUS_PORT = [string]$portalUri.Port
$process = Start-Process -FilePath (Join-Path $PSScriptRoot 'OBus.exe') -ArgumentList '--serve' -PassThru -WindowStyle Hidden
$statusUri = "http://$($portalUri.Host):$($portalUri.Port)/api/portal/thor/status"
$headers = @{ Authorization = "Bearer $($config.portal_key)" }
for ($attempt = 1; $attempt -le 60; $attempt++) {
  if ($process.HasExited) { throw "OBus portal exited before startup (code $($process.ExitCode)). Check $env:LOCALAPPDATA\Obus\logs\launcher.log" }
  try {
    Invoke-RestMethod -Uri $statusUri -Headers $headers -TimeoutSec 2 | Out-Host
    Write-Host "LOKI portal ready at $($config.loki.portal_url)"
    exit 0
  } catch {
    Start-Sleep -Milliseconds 500
  }
}
Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
throw "OBus portal did not become ready at $statusUri within 30 seconds. Check $env:LOCALAPPDATA\Obus\logs\launcher.log"
