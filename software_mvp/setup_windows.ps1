Param(
  [switch]$InstallDeps = $true,
  [switch]$InstallAutostart,
  [switch]$UseCurrentUser,
  [string]$TaskName = "EsyyB1Connector",
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host ".env creato da .env.example"
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
}

$Py = Join-Path $AppDir ".venv\Scripts\python.exe"

if ($InstallDeps) {
  & $Py -m pip install --upgrade pip
  & $Py -m pip install -r "$AppDir\requirements.txt"
}

if ($InstallAutostart) {
  $autostartParams = @{
    TaskName = $TaskName
    HostName = $HostName
    Port = $Port
  }
  if ($UseCurrentUser) {
    $autostartParams["UseCurrentUser"] = $true
  }
  & "$AppDir\install_autostart_task.ps1" @autostartParams
}

Write-Host "Setup completato."
