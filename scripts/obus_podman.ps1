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
$containerfilePath = Join-Path $repoRoot "Containerfile.podman"
$imageName = "localhost/obus-headless:pilot"
$containerName = "$ProjectName-obus-headless-1"
$volumeName = "${ProjectName}_obus_podman_state"
$networkName = "${ProjectName}_default"
$healthUri = "http://127.0.0.1:$HostPort/health"
$dashboardUri = "http://127.0.0.1:$HostPort/api/dashboard"

function Invoke-Podman {
    param([Parameter(Mandatory = $true)][string[]]$PodmanArguments)

    & podman @PodmanArguments
    if ($LASTEXITCODE -ne 0) {
        throw "podman failed with exit code $LASTEXITCODE"
    }
}

function Get-PodmanWindowsHostGateway {
    $defaultRoute = (& podman machine ssh "ip route show default" 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $defaultRoute -notmatch "default\s+via\s+(?<gateway>\S+)") {
        throw "Could not determine the Windows host gateway from the Podman machine. Output: $defaultRoute"
    }
    return $Matches.gateway
}

function Invoke-PodmanBuild {
    Invoke-Podman -PodmanArguments @(
        "build", "--format", "docker", "--file", $containerfilePath, "--tag", $imageName, $repoRoot
    )
}

function Start-ObusPilot {
    param([switch]$SkipBuild)

    if (-not $SkipBuild) {
        Invoke-PodmanBuild
    }
    $hostGateway = Get-PodmanWindowsHostGateway

    & podman volume exists $volumeName
    if ($LASTEXITCODE -ne 0) {
        Invoke-Podman -PodmanArguments @("volume", "create", $volumeName)
    }
    & podman network exists $networkName
    if ($LASTEXITCODE -ne 0) {
        Invoke-Podman -PodmanArguments @("network", "create", $networkName)
    }

    Invoke-Podman -PodmanArguments @(
        "run", "--detach", "--replace",
        "--name", $containerName,
        "--restart", "unless-stopped",
        "--network", $networkName,
        "--publish", "127.0.0.1:${HostPort}:38173",
        "--add-host", "host.containers.internal:$hostGateway",
        "--env", "HOME=/var/lib/obus",
        "--env", "OCCULTBUS_HOME=/var/lib/obus",
        "--env", "OBUS_AUTO_DELIBERATION=false",
        "--env", "OBUS_DISABLE_NATIVE_WORKSPACE_PICKER=1",
        "--env", "OBUS_OLLAMA_URL=http://host.containers.internal:11434",
        "--env", "OBUS_PROVIDER_BASE_URL=http://host.containers.internal:11434/v1",
        "--env", "COMFYUI_URL=http://host.containers.internal:8188",
        "--volume", "${volumeName}:/var/lib/obus",
        "--read-only",
        "--tmpfs", "/tmp:size=256m,mode=1777",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        $imageName
    )
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
if (-not (Test-Path -LiteralPath $containerfilePath -PathType Leaf)) {
    throw "Missing Podman container definition: $containerfilePath"
}

switch ($Action) {
    "build" {
        Invoke-PodmanBuild
    }
    "up" {
        Start-ObusPilot
        Test-ObusPilot
    }
    "down" {
        Invoke-Podman -PodmanArguments @("rm", "--force", "--ignore", $containerName)
    }
    "restart" {
        Start-ObusPilot -SkipBuild
        Test-ObusPilot
    }
    "status" {
        Invoke-Podman -PodmanArguments @("ps", "--all", "--filter", "name=^${containerName}$")
        try {
            Test-ObusPilot
        }
        catch {
            Write-Warning $_.Exception.Message
        }
    }
    "logs" {
        Invoke-Podman -PodmanArguments @("logs", "--tail", "200", "--follow", $containerName)
    }
    "verify" {
        Test-ObusPilot
    }
}
