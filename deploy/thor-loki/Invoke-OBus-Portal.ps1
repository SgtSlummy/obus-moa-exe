param(
    [Parameter(Mandatory=$true)][string]$PortalUrl,
    [Parameter(Mandatory=$true)][string]$Token,
    [string]$Prompt = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$base = $PortalUrl.TrimEnd('/')
$headers = @{ Authorization = "Bearer $Token" }

if ([string]::IsNullOrWhiteSpace($Prompt)) {
    Invoke-RestMethod -Uri "$base/api/portal/thor/status" -Headers $headers -Method Get
    return
}

$body = @{ prompt = $Prompt } | ConvertTo-Json
Invoke-RestMethod -Uri "$base/api/portal/thor/generate" -Headers $headers -Method Post -ContentType 'application/json' -Body $body
