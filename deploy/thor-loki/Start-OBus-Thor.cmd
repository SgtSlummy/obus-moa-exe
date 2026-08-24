@echo off
setlocal
set "OBUS_HOME=%~dp0"
set "OCCULTBUS_HOME=%OBUS_HOME%state"
if exist "%OBUS_HOME%voice-model-path.txt" set /p "OBUS_LOCAL_STT_MODEL_PATH="<"%OBUS_HOME%voice-model-path.txt"
start "" "%OBUS_HOME%OBus.exe"
endlocal
