[CmdletBinding()]
param(
    [ValidateSet('install', 'start', 'stop', 'restart', 'status', 'uninstall', 'dashboard', 'autostart', 'remove-autostart')]
    [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { $null }
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { throw 'Could not determine the OBus project directory.' }
$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
$Wrapper = Join-Path $ProjectRoot 'obus_bridge_service.py'
$ServiceName = 'OBusHermesBridge'
$TaskName = 'OBusHermesBridgeAutostart'
$BridgeUrl = 'http://127.0.0.1:38174'
$ObusUrl = 'http://127.0.0.1:38173'
$AutostartScript = Join-Path $ProjectRoot 'start_obus_hermes_bridge.ps1'
$StartupShortcut = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\OBus Hermes Bridge.lnk'

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Require-Admin {
    if (Test-Admin) { return }
    Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-Action',$Action) -WorkingDirectory $ProjectRoot | Out-Null
    exit 0
}
function Invoke-Wrapper([string[]]$CommandArgs) {
    if (-not (Test-Path $Python)) { throw "Python runtime not found: $Python" }
    & $Python $Wrapper @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "OBus service command failed with exit code $LASTEXITCODE." }
}
function Service-Text { return ((& sc.exe query $ServiceName 2>&1 | Out-String).Trim()) }
function Task-Text {
    try {
        $output = & schtasks.exe /Query /TN $TaskName /FO LIST 2>&1
    } catch {
        return ''
    }
    if ($LASTEXITCODE -ne 0) { return '' }
    return (($output | Out-String).Trim())
}
function Status {
    Write-Host "=== OBus Hermes Bridge ===" -ForegroundColor Cyan
    Write-Host "Bridge: $BridgeUrl"
    Write-Host "OBus:   $ObusUrl"
    $service = Service-Text
    if ($service -match 'SERVICE_NAME') { Write-Host $service } else { Write-Host 'Windows service: not installed' -ForegroundColor Yellow }
    $task = Task-Text
    if ($task -match 'TaskName:') { Write-Host "Autostart task: installed ($TaskName)" -ForegroundColor Green }
    elseif (Test-Path $StartupShortcut) { Write-Host 'Autostart: user Startup shortcut installed' -ForegroundColor Green }
    else { Write-Host 'Autostart: not installed' -ForegroundColor Yellow }
    try {
        $bridge = Invoke-RestMethod "$BridgeUrl/health" -TimeoutSec 5
        Write-Host ("Bridge status: {0}; OBus status: {1}" -f $bridge.status, $bridge.obus.status) -ForegroundColor Green
    } catch { Write-Host 'Bridge is not reachable.' -ForegroundColor Yellow }
}

function Install-Autostart {
    $taskAction = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$AutostartScript`""
    & schtasks.exe /Create /TN $TaskName /SC ONLOGON /DELAY 0000:30 /TR $taskAction /F
    if ($LASTEXITCODE -ne 0) {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($StartupShortcut)
        $shortcut.TargetPath = 'powershell.exe'
        $shortcut.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$AutostartScript`""
        $shortcut.WorkingDirectory = $ProjectRoot
        $shortcut.Save()
        Write-Host "Scheduled task denied; installed user Startup shortcut instead." -ForegroundColor Yellow
    } else {
        Write-Host "Autostart task installed: $TaskName" -ForegroundColor Green
    }
    Status
}
function Remove-Autostart {
    try { & schtasks.exe /Delete /TN $TaskName /F 2>&1 | Out-Null } catch { }
    if (Test-Path $StartupShortcut) { Remove-Item $StartupShortcut -Force }
    Write-Host 'OBus autostart removed.' -ForegroundColor Green
}

switch ($Action) {
    'install' { Require-Admin; if ((Service-Text) -match 'SERVICE_NAME') { Invoke-Wrapper @('--startup','auto','update') } else { Invoke-Wrapper @('--startup','auto','install') }; Invoke-Wrapper @('--wait','5','start'); Status }
    'start' { Require-Admin; Invoke-Wrapper @('--wait','5','start'); Status }
    'stop' { Require-Admin; Invoke-Wrapper @('--wait','5','stop'); Status }
    'restart' { Require-Admin; Invoke-Wrapper @('--wait','5','stop'); Invoke-Wrapper @('--wait','5','start'); Status }
    'status' { Status }
    'uninstall' { Require-Admin; try { Invoke-Wrapper @('--wait','5','stop') } catch {}; Invoke-Wrapper @('remove'); Status }
    'dashboard' { Start-Process $BridgeUrl }
    'autostart' { Install-Autostart }
    'remove-autostart' { Remove-Autostart }
}
