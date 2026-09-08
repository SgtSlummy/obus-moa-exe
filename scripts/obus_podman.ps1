[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("build", "up", "down", "restart", "status", "logs", "verify")]
    [string]$Action = "status",

    [ValidateRange(1024, 65535)]
    [int]$HostPort = 38183,

    [ValidatePattern("^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")]
    [string]$ProjectName = "obus-podman"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$composePath = Join-Path $repoRoot "compose.podman.yaml"
$healthUri = "http://127.0.0.1:$HostPort/health"
$dashboardUri = "http://127.0.0.1:$HostPort/api/dashboard"

function Invoke-PodmanCompose {
    param([Parameter(Mandatory = $true)][string[]]$ComposeArguments)

    & podman compose --project-name $ProjectName --file $composePath @ComposeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "podman compose failed with exit code $LASTEXITCODE"
    }
}

function Wait-ObusHealth {
    $lastError = $null
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri $healthUri -TimeoutSec 3
            if ($health.status -eq "ok") {
                return $health
            }
            $lastError = "health status was '$($health.status)'"
        }
        catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 1
    }
    throw "Podman Obus did not become healthy at $healthUri within 60 seconds. Last error: $lastError"
}

function Test-ObusPilot {
    $health = Wait-ObusHealth
    $dashboard = Invoke-RestMethod -Uri $dashboardUri -TimeoutSec 30
    $ollamaConnected = [bool]$dashboard.ollama.connected
    $models = @($dashboard.ollama.models)

    [pscustomobject]@{
        status = "ok"
        service = $health.service
        url = "http://127.0.0.1:$HostPort"
        native_service_untouched = ($HostPort -ne 38173)
        state_mode = "dedicated-podman-volume"
        ollama_connected = $ollamaConnected
        ollama_models = $models.Count
    } | ConvertTo-Json -Depth 4

    if (-not $ollamaConnected) {
        throw "Podman Obus is healthy, but it cannot reach host Ollama through host.containers.internal:11434."
    }
}

if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
    throw "Podman is not installed or is not available on PATH."
}
if (-not (Test-Path -LiteralPath $composePath -PathType Leaf)) {
    throw "Missing compose profile: $composePath"
}

$previousPort = $env:OBUS_PODMAN_PORT
$env:OBUS_PODMAN_PORT = [string]$HostPort
try {
    switch ($Action) {
        "build" {
            Invoke-PodmanCompose -ComposeArguments @("build")
        }
        "up" {
            Invoke-PodmanCompose -ComposeArguments @("up", "--detach", "--build")
            Test-ObusPilot
        }
        "down" {
            Invoke-PodmanCompose -ComposeArguments @("down", "--remove-orphans")
        }
        "restart" {
            Invoke-PodmanCompose -ComposeArguments @("restart", "obus-headless")
            Test-ObusPilot
        }
        "status" {
            Invoke-PodmanCompose -ComposeArguments @("ps")
            try {
                Test-ObusPilot
            }
            catch {
                Write-Warning $_.Exception.Message
            }
        }
        "logs" {
            Invoke-PodmanCompose -ComposeArguments @("logs", "--tail", "200", "--follow", "obus-headless")
        }
        "verify" {
            Test-ObusPilot
        }
    }
}
finally {
    if ($null -eq $previousPort) {
        Remove-Item Env:OBUS_PODMAN_PORT -ErrorAction SilentlyContinue
    }
    else {
        $env:OBUS_PODMAN_PORT = $previousPort
    }
}
