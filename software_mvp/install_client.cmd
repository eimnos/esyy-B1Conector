@echo off
setlocal EnableExtensions

set "APPDIR=%~dp0"
if "%APPDIR:~-1%"=="\" set "APPDIR=%APPDIR:~0,-1%"

echo.
echo ===============================
echo   Esyy B1Connector - Setup
echo ===============================
echo Cartella: %APPDIR%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%APPDIR%\setup_windows.ps1" -InstallDeps -InstallAutostart -TaskName "EsyyB1Connector" -HostName 127.0.0.1 -Port 8010
if errorlevel 1 (
  echo.
  echo [ERRORE] Setup non completato. Controlla output e permessi.
  pause
  exit /b 1
)

echo.
echo [OK] Setup completato.
echo Apri il browser su: http://127.0.0.1:8010/login
pause
