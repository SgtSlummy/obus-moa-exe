# OBus Thor → Loki Deployment

This package installs the OBus standalone application on **Thor** in primary mode.
It seeds a Loki worker target at Tailscale IP `100.73.36.108` and keeps remote-terminal activation disabled until Thor has an approved SSH account and local identity-file reference.

## Included capabilities

- Text chat and dynamic Tarot/Key agent harness.
- Output-first dashboard with selectable all-card assignment previews.
- Local voice transcription support when Thor already has a Faster-Whisper model directory.
- Primary/worker setup state: Thor = primary, Loki = worker.
- Non-destructive Tailscale + port-22 route test.

## Install on Thor

1. Copy this entire folder to Thor.
2. Run PowerShell from the folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-OBus-Thor.ps1
```

3. For local voice, pass the path to an already present Faster-Whisper model directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-OBus-Thor.ps1 -LocalSttModelPath "D:\Models\faster-whisper-base"
```

4. Start text and voice OBus through `Start-OBus-Thor.cmd`.

## Verify the Loki route

Run this from Thor only after both machines are connected to the same Tailscale network:

```powershell
powershell -ExecutionPolicy Bypass -File .\Test-Loki-Route.ps1
```

The route test checks Tailscale reachability and TCP port 22. It does not launch a remote terminal or inspect identity files.

## Remote terminal activation

The package records Loki as the worker target but does not configure a live remote shell. Before enabling one, choose the Thor-side SSH account and the local identity-file reference that is authorized for Loki. Never place credentials or key material in this package or in OBus state.
