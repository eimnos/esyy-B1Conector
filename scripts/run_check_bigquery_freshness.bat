@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%bigquery_freshness_log.txt"
set "PYTHON_EXE=C:\Users\datalab2\AppData\Local\Python\pythoncore-3.14-64\python.exe"

if not exist "%PYTHON_EXE%" (
  set "PYTHON_EXE=python"
)

echo ==================================================>> "%LOG_FILE%"
echo Avvio controllo BigQuery %date% %time%>> "%LOG_FILE%"
"%PYTHON_EXE%" "%SCRIPT_DIR%check_bigquery_freshness.py" --threshold-hours 24 >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=!ERRORLEVEL!"
if "!EXIT_CODE!"=="" set "EXIT_CODE=1"
echo Fine controllo BigQuery %date% %time% - ExitCode=!EXIT_CODE!>> "%LOG_FILE%"
echo.>> "%LOG_FILE%"

exit /b !EXIT_CODE!
