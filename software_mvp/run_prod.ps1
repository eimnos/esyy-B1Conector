Param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8010,
  [switch]$InstallDeps
)

$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
}

$Py = Join-Path $AppDir ".venv\Scripts\python.exe"

if ($InstallDeps) {
  & $Py -m pip install --upgrade pip
  & $Py -m pip install -r "$AppDir\requirements.txt"
}

& $Py -m uvicorn app.main:app --app-dir "$AppDir" --host $HostName --port $Port
