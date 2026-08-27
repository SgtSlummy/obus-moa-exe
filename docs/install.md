# Install Obus

## Recommended Windows install

1. Open the repository's **Releases** page and download `Obus.exe` plus `SHA256SUMS.txt` from the newest release.
2. Verify the download before running it:

   ```powershell
   Get-FileHash .\Obus.exe -Algorithm SHA256
   Get-AuthenticodeSignature .\Obus.exe | Format-List Status,SignerCertificate
   ```

   The hash must match `SHA256SUMS.txt`. A production-certified release reports `Status: Valid` and the expected publisher. An unsigned development release reports `NotSigned`; do not interpret an unsigned build as certified.
3. Move `Obus.exe` to a stable per-user location such as `%LOCALAPPDATA%\Programs\Obus\Obus.exe`. Launch-at-login stores this exact path, so do not move the file afterward.
4. Run `codex login`, then open `Obus.exe`. The dashboard opens after the local health check succeeds.
5. Use the Obus notification-area icon to **Open Obus**, toggle **Start with Windows**, or **Exit**. Startup launches silently into the tray and does not open a browser.

Obus listens on loopback at `http://127.0.0.1:38173` and stores runtime state under `OCCULTBUS_HOME` (default `~/.occultbus`).

## Install from source

```powershell
git clone https://github.com/SgtSlummy/obus-moa-exe.git
cd obus-moa-exe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
codex login
python -m uvicorn backend.main:app --host 127.0.0.1 --port 38173
```

Build and install the Windows desktop executable, Start Menu shortcut, and per-user launch-at-login entry:

```powershell
python -m pip install pyinstaller
.\tools\obus_launcher\build_and_install.ps1
```

The script builds the complete root `OBus.spec` from a project runtime, preferring `.build-venv` and then `.venv`; it never falls back to an arbitrary `python` found on `PATH`. Use `-PythonPath` only with the full path to a project environment that already has OBus's dependencies installed.

## Uninstall

Choose **Exit** from the tray, turn off **Start with Windows** first, and delete the installed executable and Start Menu shortcut. Runtime data is intentionally retained; remove the `OCCULTBUS_HOME` directory only when you explicitly want to erase Obus state.
