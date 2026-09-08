# Podman headless-core pilot

The Podman profile runs the cross-platform FastAPI core in a hardened Linux container while leaving the Windows-owned integrations on the host. It is a parallel pilot, not a replacement for the healthy native service.

## Boundary

Containerized:

- FastAPI backend and static operator UI
- isolated Python dependencies
- dedicated persistent state volume
- health and restart lifecycle
- HTTP access to host Ollama and ComfyUI status

Kept native on Windows:

- Electron, notification-area lifecycle, and installed shortcuts
- Codex CLI OAuth and Codex subprocess execution
- MCP stdio facade and Hermes bridge
- PowerShell/cmd terminal sessions and native workspace picker
- Ollama GPU inference and ComfyUI process ownership

The pilot intentionally uses a new state volume instead of mounting the native `OCCULTBUS_HOME`. Running two backends against one writable state directory is unsupported.

## Start and verify

Podman Desktop or a running Podman machine is required. From the repository root:

```powershell
.\scripts\obus_podman.ps1 up
```

This builds `localhost/obus-headless:pilot`, starts it at <http://127.0.0.1:38183>, waits for `/health`, and verifies that the container can reach host Ollama. The native Obus service on `38173` is not stopped or reconfigured.

Other commands:

```powershell
.\scripts\obus_podman.ps1 status
.\scripts\obus_podman.ps1 verify
.\scripts\obus_podman.ps1 logs
.\scripts\obus_podman.ps1 restart
.\scripts\obus_podman.ps1 down
```

`down` preserves the named state volume. Removing that volume is deliberately not part of the helper because it destroys pilot state.

Use `-HostPort <port>` to run the pilot on another loopback port. The default is `38183`.

## Connect native clients to the pilot

Start a client with a temporary loopback override. Do not change the installed application's permanent configuration until the pilot passes the required parity checks.

Electron development shell:

```powershell
$env:OBUS_URL = "http://127.0.0.1:38183/"
npm --prefix electron_app start
```

Secondary Hermes bridge:

```powershell
$env:OBUS_URL = "http://127.0.0.1:38183"
$env:OBUS_BRIDGE_PORT = "38184"
python .\obus_hermes_bridge.py
```

Codex can use the existing host-side MCP facade against the pilot only when Codex is started with `OBUS_URL=http://127.0.0.1:38183`. The stdio facade stays native; it is not installed in the container.

## Expected limitations

The container does not contain the Windows Codex CLI session or expose a host filesystem shell. Codex-provider execution, native terminal sessions, native folder selection, and starting Windows applications should therefore report unavailable from the container profile. Local Ollama routing and remote HTTP providers can work normally when explicitly configured.

The Compose profile publishes only to Windows loopback, drops Linux capabilities, enables `no-new-privileges`, uses a read-only root filesystem, and keeps secrets out of the manifest. Add provider credentials later through an external secret or environment manager; do not write them into the Compose file.

## Cutover criteria

Keep the native service as the default until all of these are demonstrated against the pilot:

1. `/health` remains healthy through restart.
2. `/api/dashboard` reports host Ollama connected.
3. Local Ollama route planning and execution pass.
4. Persistent pilot state survives container recreation.
5. Electron can attach through `OBUS_URL` without spawning another backend.
6. Every intentionally unsupported Windows feature fails clearly without affecting core health.

Only after those checks should a separate decision consider moving the default port or startup ownership.
