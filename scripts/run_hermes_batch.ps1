param(
    [string]$BatchFile = "$PSScriptRoot\obus-hermes-batch.json",
    [string]$OutputDir = "$PSScriptRoot\..\data\hermes-batch-results",
    [string]$Profile = "",
    [string]$Toolsets = "terminal,file,coding",
    [string]$Provider = "",
    [string]$Model = "",
    [int]$MaxTurns = 30,
    [switch]$Worktree,
    [switch]$AcceptHooks,
    [switch]$Sequential,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$hermesCommand = Get-Command hermes -ErrorAction SilentlyContinue
if (-not $hermesCommand) {
    throw "Hermes CLI was not found on PATH. Run 'hermes doctor' first."
}

if (-not (Test-Path -LiteralPath $BatchFile)) {
    throw "Batch file not found: $BatchFile"
}

$parsedBatch = Get-Content -LiteralPath $BatchFile -Raw | ConvertFrom-Json
$jobs = @()
foreach ($entry in $parsedBatch) {
    $jobs += $entry
}
if ($jobs.Count -eq 0) {
    throw "Batch file contains no jobs."
}

function Quote-ProcessArgument([string]$Value) {
    return '"' + $Value.Replace('"', '\"') + '"'
}

$resolvedOutput = [IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

$running = @()
foreach ($job in $jobs) {
    if ([string]::IsNullOrWhiteSpace($job.id) -or [string]::IsNullOrWhiteSpace($job.prompt)) {
        throw "Every batch job must have non-empty id and prompt fields."
    }

    $safeId = ($job.id -replace '[^A-Za-z0-9_.-]', '_')
    $stdout = Join-Path $resolvedOutput "$safeId.out.txt"
    $stderr = Join-Path $resolvedOutput "$safeId.err.txt"
    $arguments = @()
    $jobProfile = if ($job.profile) { [string]$job.profile } else { $Profile }

    if ($jobProfile) {
        $arguments += @('--profile', $jobProfile)
    }
    if ($Worktree) {
        $arguments += '--worktree'
    }
    if ($Provider) {
        $arguments += @('--provider', $Provider)
    }
    if ($Model) {
        $arguments += @('-m', $Model)
    }
    $arguments += @('chat', '-q', $job.prompt, '-Q', '--toolsets', $Toolsets, '--max-turns', "$MaxTurns", '--source', "batch:$safeId")
    if ($AcceptHooks) {
        $arguments += '--accept-hooks'
    }

    $argumentString = ($arguments | ForEach-Object { Quote-ProcessArgument ([string]$_) }) -join ' '
    Write-Host "[$safeId] hermes $argumentString"

    if ($DryRun) {
        continue
    }

    if ($Sequential) {
        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $hermesCommand.Source @arguments 1> $stdout 2> $stderr
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorAction
        Write-Host "[$safeId] exit code $exitCode"
        $running += [PSCustomObject]@{
            Id = $safeId
            Process = $null
            ExitCode = $exitCode
            Stdout = $stdout
            Stderr = $stderr
        }
        continue
    }

    $process = Start-Process `
        -FilePath $hermesCommand.Source `
        -ArgumentList $argumentString `
        -WorkingDirectory (Get-Location).Path `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru

    if ($Sequential) {
        $process.WaitForExit()
        Write-Host "[$safeId] exit code $($process.ExitCode)"
    }

    $running += [PSCustomObject]@{
        Id = $safeId
        Process = $process
        ExitCode = $null
        Stdout = $stdout
        Stderr = $stderr
    }
}

if ($DryRun) {
    Write-Host "Dry run complete. $($jobs.Count) jobs were not started."
    exit 0
}

foreach ($item in $running) {
    if ($item.Process) {
        $item.Process.WaitForExit()
        $item.ExitCode = $item.Process.ExitCode
        Write-Host "[$($item.Id)] exit code $($item.ExitCode)"
    }
}

$summary = @($running | ForEach-Object {
    [PSCustomObject]@{
        id = $_.Id
        exit_code = $_.ExitCode
        stdout = $_.Stdout
        stderr = $_.Stderr
    }
})
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $resolvedOutput "summary.json") -Encoding UTF8
Write-Host "Batch complete. Results: $resolvedOutput"
