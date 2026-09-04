# Windows installer

## Current verified artifact

- Installer: `C:\Users\Hermes\Documents\obus-moa-exe\installers\windows\OBus-Setup-1.0.0-x64.exe`
- Built on: LOKI, 2026-08-27
- Size: 76,165,750 bytes
- SHA-256: `804940FBF8DCD2272F9F5C9DF98BDB47414166A6E11ED1CA05816FD19C3B7561`
- Format: NSIS, Windows x64, per-user install
- Signing: unsigned development build

## Rebuild

From `C:\Users\Hermes\Documents\obus-moa-exe\electron_app`:

```powershell
npm install
npm run dist:win
```

The build writes the installer and block map to `installers\windows`.

## LOKI verification

The installer was smoke-tested on LOKI with an isolated per-user target under `%LOCALAPPDATA%\Temp`:

- Silent installer exit code: `0`
- Installed executable present: yes
- First launch remained running: yes (four Electron processes)
- Main window title: `OBus MOA`
- Live backend used for first run: `http://127.0.0.1:38173/health` returned `{"status":"ok","service":"obus-moa"}`
- Silent uninstaller exit code: `0`
- Isolated smoke-test installation removed after verification: yes

The initial build failure was corrected by declaring Electron as a development dependency and adding a checked-in `electron-builder` NSIS configuration.
