# Obus

Obus is a local-first full-stack agent workspace with a FastAPI backend, browser-based operator UI, persistent local state, desktop launcher, and multi-provider agent runtime. AutoAgent is the default primary autonomous harness; Codex is its secondary fallback and remains available for explicit selection.

## Requirements

- Python 3.12 or newer
- Codex CLI for the default agent workflow
- Windows for the packaged desktop executable
- Optional: Ollama, provider API credentials, ComfyUI, NVIDIA Warp, and GitHub App credentials

## Install

For the packaged Windows app, checksum and signature verification, launch-at-login, source installation, and uninstall steps, see [docs/install.md](docs/install.md).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
codex login status
python -m uvicorn backend.main:app --host 127.0.0.1 --port 38173
```

Open <http://127.0.0.1:38173>. Runtime data is stored outside the repository under `OCCULTBUS_HOME` (default: `~/.occultbus`).

On macOS or Linux, activate with `source .venv/bin/activate`; desktop packaging is Windows-specific, but the web application is cross-platform.

## AutoAgent-primary harness with Codex fallback

Install [HKUDS AutoAgent](https://github.com/HKUDS/AutoAgent) in a dedicated environment and make its `auto` command available on `PATH`. Obus invokes AutoAgent's non-interactive `auto agent` command with `get_system_triage_agent` by default. Set `OBUS_AUTOAGENT_AGENT_FUNCTION` only when you have verified a different AutoAgent agent function in your installation.

```powershell
git clone https://github.com/HKUDS/AutoAgent.git
cd AutoAgent
python -m pip install -e .
```

For every ordinary harness task, Obus starts AutoAgent first. If it is unavailable or fails, Obus emits a `provider.fallback` event and uses Codex. Set `OBUS_AUTOAGENT_FALLBACK_CODEX=false` to require AutoAgent instead. Codex (`key-codex-oauth`) remains available for explicit selection and fallback; existing explicit provider selections are preserved.

```powershell
codex --version
codex login
codex login status
```

Obus delegates authentication to the Codex CLI. Do not paste OAuth credentials into Obus. The UI reports Codex availability and login state and retains alternative providers for explicit selection.

## Configuration

Copy `.env.example` into your environment manager or shell profile and set only the values you need. Obus never requires provider secrets to be committed. Important settings include:

- `OCCULTBUS_HOME`: persistent state directory
- `OBUS_AUTO_DELIBERATION`: opt-in background deliberation
- `OBUS_PROVIDER_BASE_URL`: OpenAI-compatible provider endpoint
- `OBUS_OLLAMA_KEEP_ALIVE`: Ollama model lifetime
- `MOA_ROUTER_ROOT`: optional local MoA router checkout
- Provider credential variables listed in `.env.example`

## Verification

```powershell
python -m compileall -q backend tools scripts
python -m pytest -q
python -m pytest -q tools/obus_launcher/test_obus_launcher.py
python -m pip_audit
```

The two pytest commands are intentionally separate because the repository root launcher and desktop launcher module share a name.

For a release-facing OBus-versus-Codex comparison, use the versioned parity
matrix described in [docs/obus-codex-comparison.md](docs/obus-codex-comparison.md):

```powershell
python scripts/obus_codex_comparison.py --plan
```

## Production build

Build without installing or changing Desktop/Start Menu state:

```powershell
python -m pip install pyinstaller
.\tools\obus_launcher\build_and_install.ps1 -SkipInstall
```

The build script uses the first available project runtime—`.build-venv` then `.venv`—rather than whatever Python happens to be on `PATH`. Pass the full path with `-PythonPath` only when deliberately building from another fully provisioned project environment. The verified artifact is written to `tools/obus_launcher/dist/Obus.exe` and its SHA-256 is printed. Omit `-SkipInstall` to install the executable and Start Menu shortcut. The packaged app remains in the Windows notification area; its menu opens Obus, toggles per-user **Start with Windows**, and exits the launcher-owned backend cleanly.

Tagging a release with `v*` invokes the release workflow, reruns all gates, builds the executable, optionally Authenticode-signs it, verifies the signature, and publishes the executable and checksum. A trusted public build requires the repository signing secrets described in [docs/release.md](docs/release.md).

## GitHub App integration

To register a least-privilege GitHub App for repository memory synchronization, see [docs/github-app.md](docs/github-app.md). GitHub App registration and Windows executable certification are separate trust systems.

## Thor portal

The packaged EXE can expose this PC's installed Ollama models to Thor through a bearer-authenticated, capability-limited portal while keeping the dashboard, filesystem, and inference local. See [docs/thor-portal.md](docs/thor-portal.md).

## Architecture and operations

See [docs/architecture.md](docs/architecture.md) for component boundaries and [docs/release.md](docs/release.md) for release, deployment, startup, health, shutdown, and rollback procedures.

## Security

Obus binds locally by default, keeps state outside the repository, supports a machine-bound local access gate, validates provider base URLs, redacts secret-shaped data, and uses atomic persistence. Never commit `.env`, access tokens, provider credentials, local state, build outputs, or virtual environments.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). CI performs clean installation, compilation, application and launcher tests, dependency auditing, and Windows executable packaging.
