param(
    [switch]$RotateToken
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$current = [Environment]::GetEnvironmentVariable('OBUS_THOR_TOKEN', 'User')
if ($RotateToken -or [string]::IsNullOrWhiteSpace($current) -or $current.Length -lt 32) {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $current = [Convert]::ToBase64String($bytes)
    [Environment]::SetEnvironmentVariable('OBUS_THOR_TOKEN', $current, 'User')
}
[Environment]::SetEnvironmentVariable('OBUS_HOST', '0.0.0.0', 'User')

Write-Host 'Obus Thor portal enabled for this Windows user.'
Write-Host 'Restart Obus from the tray so it reads the new configuration.'
Write-Host 'Transfer this token to Thor through an approved secure channel; it will not be written to the repository:'
Write-Output $current
