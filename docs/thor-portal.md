# Thor local-resource portal

The Obus EXE can act as a thin, authenticated portal so Thor uses this PC's Ollama models while inference and resource ownership remain on this machine. It does not grant Thor a shell, arbitrary filesystem access, or unrestricted Obus dashboard access.

## Enable on the resource PC

Run from the repository or deployment bundle:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\thor-loki\Enable-OBus-Thor-Portal.ps1
```

The script creates a 256-bit bearer token and stores `OBUS_HOST=0.0.0.0` and `OBUS_THOR_TOKEN` in the current user's environment. Transfer the displayed token to Thor through an approved secure channel, then exit and restart Obus from the tray. Use `-RotateToken` to revoke the previous token.

Connect the machines with a private network such as Tailscale. Allow inbound TCP 38173 only from Thor's private/Tailscale address in Windows Firewall. Do not expose port 38173 directly to the public internet.

## Use from Thor

```powershell
.\Invoke-OBus-Portal.ps1 -PortalUrl 'http://RESOURCE-PC-TAILSCALE-IP:38173' -Token $env:OBUS_THOR_TOKEN
.\Invoke-OBus-Portal.ps1 -PortalUrl 'http://RESOURCE-PC-TAILSCALE-IP:38173' -Token $env:OBUS_THOR_TOKEN -Prompt 'Summarize this task locally'
```

Direct API contracts:

- `GET /api/portal/thor/status`
- `POST /api/portal/thor/generate` with `{ "prompt": "...", "model": "optional-installed-model" }`
- `Authorization: Bearer <32-or-more-character-token>` is mandatory

The portal accepts only installed local Ollama models. Its advertised capabilities are currently `llm.generate`, `llm.models`, and `system.health`. All non-portal routes reject non-loopback clients, so the EXE remains a portal rather than a remote-control surface.

## Disable

Exit Obus, then remove the two user variables and restart:

```powershell
[Environment]::SetEnvironmentVariable('OBUS_HOST', $null, 'User')
[Environment]::SetEnvironmentVariable('OBUS_THOR_TOKEN', $null, 'User')
```

Remove the associated narrow Windows Firewall rule if one was created.
