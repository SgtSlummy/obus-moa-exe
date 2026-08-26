@echo off
rem Start the OBus backend and open the Electron wrapper.
rem Assumes npm and electron are installed locally.

:: Launch the backend in a separate terminal window
start cmd /k "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"

:: Give the server a moment to bind
ping 127.0.0.1 -n 3 > nul

:: Change to the Electron app directory and launch Electron
pushd "%~dp0electron_app"
electron .
popd
