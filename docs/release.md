# Release and deployment

## Release gate

Run from a clean checkout with Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest pip-audit pyinstaller
.\.venv\Scripts\python.exe -m compileall -q backend tools scripts
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q tools/obus_launcher/test_obus_launcher.py
.\.venv\Scripts\python.exe -m pip_audit
.\tools\obus_launcher\build_and_install.ps1 -SkipInstall -PythonPath .\.venv\Scripts\python.exe
```

The release is rejected if any command fails, the artifact is missing, secrets appear in tracked files, or the worktree includes generated output.

## Artifact verification

The build prints the SHA-256 of `tools/obus_launcher/dist/Obus.exe`. Record it in the GitHub release and verify downloaded artifacts with:

```powershell
Get-FileHash .\Obus.exe -Algorithm SHA256
```

GitHub Actions uploads the Windows executable produced by the same non-installing build path.

## Certified Windows releases

Windows publisher trust is established with an Authenticode code-signing certificate issued to the publisher by a trusted certificate authority. Repository code cannot self-issue that identity or bypass SmartScreen reputation.

Configure these GitHub Actions repository secrets before publishing a certified build:

- `WINDOWS_CERTIFICATE_BASE64`: base64 encoding of the password-protected `.pfx` certificate
- `WINDOWS_CERTIFICATE_PASSWORD`: the PFX password

Create the base64 value locally without printing the password:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes('publisher-certificate.pfx')) | Set-Clipboard
```

Push an annotated `v*` tag only after the secrets are configured. `.github/workflows/release.yml` verifies source, builds `Obus.exe`, signs with SHA-256 and a trusted timestamp, rejects an invalid configured signature, and publishes `Obus.exe`, `SHA256SUMS.txt`, and `signature.txt` to a GitHub Release. Releases are allowed to remain unsigned only when the certificate secret is absent, and `signature.txt` makes that status explicit.

For stronger key isolation, replace the exported PFX step with the certificate authority's hardware-token or managed signing action. Protect the release environment, restrict secret access, require tag review, and never store a PFX or password in the repository.

## Publishing

```powershell
git tag -a v1.0.0 -m "Obus 1.0.0"
git push origin v1.0.0
```

Confirm the release workflow is green, download its assets, independently verify the checksum and `Get-AuthenticodeSignature`, then publish the release URL. See [install.md](install.md) for user-facing installation steps and [github-app.md](github-app.md) for the separate GitHub App registration process.

## Source deployment

Run behind the local access boundary on loopback:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 38173 --log-level info
```

If remote exposure is required, place Obus behind a trusted TLS reverse proxy and enforce network authentication. Do not bind publicly with the development configuration.

## Health and startup

Poll `GET /health`; HTTP 200 is the readiness condition. Do not gate readiness on optional providers or model warmup. The launcher opens the UI after health succeeds and reports actionable failure when the timeout expires.

## Shutdown and recovery

Use Ctrl+C for foreground deployments or the service manager's normal stop operation. Wait for process exit before replacing an executable or state directory. If startup fails:

1. Check `/health` and the bound port.
2. Confirm the selected Python environment and installed dependencies.
3. Run `codex login status` for the primary-agent workflow.
4. Temporarily disable optional integrations rather than deleting state.
5. Restore the previous executable and verify its recorded hash.

State is stored under `OCCULTBUS_HOME`; back it up before migration. Atomic writes protect against partial JSON files, but backups remain the rollback authority.

## Release checklist

- CI is green on Windows and Linux.
- Clean installation, application tests and launcher tests pass.
- Dependency audit reports no known vulnerabilities.
- Codex login and a read-only execution succeed.
- Cold health timing and packaged smoke test are recorded.
- `git diff --check` succeeds and no secrets/generated files are tracked.
- Version and release notes describe migrations and known optional-integration limitations.
