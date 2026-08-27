param(
    [switch]$SkipInstall,
    [string]$PythonPath = "",
    [string]$OutputDirectory = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$launcherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path (Split-Path $launcherDir -Parent) -Parent
$projectInterpreters = @(
    (Join-Path $repoRoot ".build-venv\Scripts\python.exe"),
    (Join-Path $repoRoot ".venv\Scripts\python.exe")
)
$python = if ($PythonPath) { $PythonPath } else { $projectInterpreters | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1 }
$testFile = Join-Path $launcherDir "test_obus_launcher.py"
$spec = Join-Path $repoRoot "OBus.spec"
$dist = if ($OutputDirectory) {
    if ([System.IO.Path]::IsPathRooted($OutputDirectory)) { $OutputDirectory } else { Join-Path $repoRoot $OutputDirectory }
} else { Join-Path $launcherDir "dist" }
$work = Join-Path $launcherDir "build"
$installDir = Join-Path $env:LOCALAPPDATA "Programs\Obus"
$deployedExe = Join-Path $installDir "Obus.exe"
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$startMenuShortcut = Join-Path $startMenu "Obus.lnk"
$startupRegistryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

if (-not $python -or -not (Test-Path -LiteralPath $python)) {
    throw "Expected a project Python runtime at .build-venv or .venv, or pass -PythonPath with its full path."
}
if (-not (Test-Path -LiteralPath $spec)) {
    throw "Expected complete desktop build spec was not found: $spec"
}

Push-Location $repoRoot
try {
    & $python $testFile -v
    if ($LASTEXITCODE -ne 0) { throw "Launcher tests failed." }

    # Freeze with the complete root spec so tray, terminal, local voice, and every
    # packaged static asset are sourced from this interpreter's installed modules.
    & $python -m PyInstaller $spec --noconfirm --clean --distpath $dist --workpath $work --log-level ERROR
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
}
finally {
    Pop-Location
}

$builtExe = Join-Path $dist "Obus.exe"
if (-not (Test-Path $builtExe)) { throw "PyInstaller did not produce $builtExe" }
$sourceHash = (Get-FileHash $builtExe -Algorithm SHA256).Hash

if ($SkipInstall) {
    Write-Host "Built release artifact: $builtExe"
    Write-Host "SHA-256: $sourceHash"
    return
}

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item $builtExe $deployedExe -Force
$installedHash = (Get-FileHash $deployedExe -Algorithm SHA256).Hash
if ($sourceHash -ne $installedHash) { throw "Installed EXE hash does not match the verified build." }

New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($startMenuShortcut)
$shortcut.TargetPath = $deployedExe
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = "$deployedExe,0"
$shortcut.Description = "Launch the local OBus dashboard"
$shortcut.Save()

New-Item -Path $startupRegistryPath -Force | Out-Null
Set-ItemProperty -Path $startupRegistryPath -Name "Obus" -Value "`"$deployedExe`" --startup"

Write-Host "Built and installed: $deployedExe"
Write-Host "Start Menu shortcut: $startMenuShortcut"
Write-Host "Launch at login: enabled (system tray)"
Write-Host "SHA-256: $installedHash"
