# Obus

Obus is a local-first full-stack agent workspace with a FastAPI backend, browser-based operator UI, persistent local state, desktop launcher, and multi-provider agent runtime. Codex is the default primary agent; other configured providers remain available.

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

## Codex-first operation

Codex (`key-codex-oauth`) is the default aggregator and primary runtime key for new or implicit state. Existing explicit provider selections are preserved.

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

## Production build

Build without installing or changing Desktop/Start Menu state:

```powershell
python -m pip install pyinstaller
.\tools\obus_launcher\build_and_install.ps1 -SkipInstall -PythonPath python
```

The verified artifact is written to `tools/obus_launcher/dist/Obus.exe` and its SHA-256 is printed. Omit `-SkipInstall` to install the executable and Start Menu shortcut using the project `.venv`. The packaged app remains in the Windows notification area; its menu opens Obus, toggles per-user **Start with Windows**, and exits the launcher-owned backend cleanly.

Tagging a release with `v*` invokes the release workflow, reruns all gates, builds the executable, optionally Authenticode-signs it, verifies the signature, and publishes the executable and checksum. A trusted public build requires the repository signing secrets described in [docs/release.md](docs/release.md).

## GitHub App integration

To register a least-privilege GitHub App for repository memory synchronization, see [docs/github-app.md](docs/github-app.md). GitHub App registration and Windows executable certification are separate trust systems.

## Architecture and operations

See [docs/architecture.md](docs/architecture.md) for component boundaries and [docs/release.md](docs/release.md) for release, deployment, startup, health, shutdown, and rollback procedures.

## Security

Obus binds locally by default, keeps state outside the repository, supports a machine-bound local access gate, validates provider base URLs, redacts secret-shaped data, and uses atomic persistence. Never commit `.env`, access tokens, provider credentials, local state, build outputs, or virtual environments.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). CI performs clean installation, compilation, application and launcher tests, dependency auditing, and Windows executable packaging.
