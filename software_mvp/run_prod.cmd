@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "APPDIR=%~dp0"
if "%APPDIR:~-1%"=="\" set "APPDIR=%APPDIR:~0,-1%"
cd /d "%APPDIR%"

set "HOST=%~1"
if "%HOST%"=="" set "HOST=127.0.0.1"

set "PORT=%~2"
if "%PORT%"=="" set "PORT=8010"

set "PY=%APPDIR%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [ERROR] Python venv non trovato: "%PY%"
  echo Esegui prima setup_windows.ps1 oppure install_client.cmd
  exit /b 1
)

set "LOGDIR=%APPDIR%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

set "OUTLOG=%LOGDIR%\uvicorn_out.log"
set "ERRLOG=%LOGDIR%\uvicorn_err.log"
set "RESTART_DELAY_SECONDS=5"

echo [%date% %time%] Avvio loop Esyy B1Connector host=%HOST% port=%PORT% >> "%OUTLOG%"

:loop
echo [%date% %time%] START uvicorn >> "%OUTLOG%"
"%PY%" -m uvicorn app.main:app --app-dir "%APPDIR%" --host %HOST% --port %PORT% --log-level info 1>> "%OUTLOG%" 2>> "%ERRLOG%"
set "EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] STOP uvicorn exit_code=%EXIT_CODE% - restart in %RESTART_DELAY_SECONDS%s >> "%OUTLOG%"
timeout /t %RESTART_DELAY_SECONDS% /nobreak >nul
goto loop
