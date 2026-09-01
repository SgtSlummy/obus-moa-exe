# Desktop Launch with Uvicorn

Use this batch script to launch OBus quickly and reliably:

```cmd
@echo off
set REPO_ROOT=C:\Users\Hermes\Documents\obus-moa-exe
pushd "%REPO_ROOT%"

rem kill stale uvicorn
tasklist /FI "IMAGENAME eq uvicorn.exe" 2>NUL | find /I "uvicorn.exe" >NUL
if %ERRORLEVEL%==0 (
    echo Killing stale uvicorn...
    taskkill /F /IM uvicorn.exe
)

rem start backend
echo Starting OBus backend...
start "" /B python -m uvicorn backend.main:app --host 127.0.0.1 --port 38174 --log-level info > "%REPO_ROOT%/logs/obus_backlog.txt" 2>&1

popd
```

* The script should be saved as `C:\Users\Hermes\Documents\obus-moa-exe\scripts\start_obus.cmd`.
* Pin the shortcut to the Desktop and use the icon `C:\Users\Hermes\Documents\obus-moa-exe\obus-emblem-icon.ico`.
* The logs are written to `logs/obus_backlog.txt` for debugging.

## Tips
- The launcher kills any stale uvicorn before starting a new one.
- No terminal window is shown (`/B`).
- You can add `--reload` for dev; remove it for production.
