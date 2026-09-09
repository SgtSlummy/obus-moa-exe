@echo off
rem The desktop and local API clients share the same loopback runtime.
powershell.exe -NoProfile -File "%~dp0start_obus_hermes_bridge.ps1"
pushd "%~dp0electron_app"
call npm start
popd
