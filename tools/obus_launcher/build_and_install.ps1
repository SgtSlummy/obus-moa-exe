param(
    [switch]$SkipInstall,
    [string]$PythonPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$launcherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path (Split-Path $launcherDir -Parent) -Parent
$python = if ($PythonPath) { $PythonPath } else { Join-Path $repoRoot ".venv\Scripts\python.exe" }
$entryPoint = Join-Path $launcherDir "obus_launcher.py"
$testFile = Join-Path $launcherDir "test_obus_launcher.py"
$icon = Join-Path $launcherDir "obus.ico"
$dist = Join-Path $launcherDir "dist"
$work = Join-Path $launcherDir "build"
$desktop = [Environment]::GetFolderPath("Desktop")
$deployedExe = Join-Path $desktop "Obus.exe"
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$startMenuShortcut = Join-Path $startMenu "Obus.lnk"

if (-not $PythonPath -and -not (Test-Path $python)) {
    throw "Expected project interpreter was not found: $python"
}

Push-Location $repoRoot
try {
    & $python $testFile -v
    if ($LASTEXITCODE -ne 0) { throw "Launcher tests failed." }

    & $python (Join-Path $launcherDir "build_icon.py")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $icon)) { throw "Icon build failed." }

    & $python -m PyInstaller --noconfirm --clean --onefile --windowed --name Obus --icon $icon `
        --add-data "$repoRoot\backend\static;backend\static" `
        --hidden-import backend.main `
        --distpath $dist --workpath $work --specpath $launcherDir $entryPoint
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

Copy-Item $builtExe $deployedExe -Force
$desktopHash = (Get-FileHash $deployedExe -Algorithm SHA256).Hash
if ($sourceHash -ne $desktopHash) { throw "Desktop EXE hash does not match the verified build." }

New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($startMenuShortcut)
$shortcut.TargetPath = $deployedExe
$shortcut.WorkingDirectory = $desktop
$shortcut.IconLocation = "$deployedExe,0"
$shortcut.Description = "Launch the local OBus dashboard"
$shortcut.Save()

Write-Host "Built and deployed: $deployedExe"
Write-Host "Start Menu shortcut: $startMenuShortcut"
Write-Host "SHA-256: $desktopHash"