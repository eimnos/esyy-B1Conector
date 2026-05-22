Param(
  [string]$Version = (Get-Date -Format "yyyy.MM.dd_HHmm"),
  [string]$OutputDir = ".\dist\installer",
  [string]$PayloadDir = ".\dist\installer_payload"
)

$ErrorActionPreference = "Stop"

function Resolve-IsccPath {
  $cmd = Get-Command iscc -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $candidates = @(
    "$env:LOCALAPPDATA\\Programs\\Inno Setup 6\\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    "C:\Program Files\Inno Setup 5\ISCC.exe"
  )

  foreach ($path in $candidates) {
    if (Test-Path $path) { return $path }
  }

  throw "ISCC.exe non trovato. Installa Inno Setup 6: https://jrsoftware.org/isdl.php"
}

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

$OutAbs = Resolve-Path -Path $OutputDir -ErrorAction SilentlyContinue
if (-not $OutAbs) {
  New-Item -ItemType Directory -Path $OutputDir | Out-Null
  $OutAbs = Resolve-Path -Path $OutputDir
}

$PayloadAbs = Resolve-Path -Path $PayloadDir -ErrorAction SilentlyContinue
if (-not $PayloadAbs) {
  New-Item -ItemType Directory -Path $PayloadDir | Out-Null
  $PayloadAbs = Resolve-Path -Path $PayloadDir
}

$VersionSafe = ($Version -replace "[^0-9A-Za-z._-]", "_")
$StageDir = Join-Path $PayloadAbs ("esyy_b1connector_" + $VersionSafe)

if (Test-Path $StageDir) {
  Remove-Item -Recurse -Force $StageDir
}
New-Item -ItemType Directory -Path $StageDir | Out-Null

$include = @(
  "app",
  "requirements.txt",
  "README.md",
  ".env.example",
  "run_prod.cmd",
  "run_prod.ps1",
  "run_dev.ps1",
  "setup_windows.ps1",
  "install_autostart_task.ps1",
  "uninstall_autostart_task.ps1",
  "install_client.cmd",
  "installer\\assets"
)

foreach ($item in $include) {
  Copy-Item -Path (Join-Path $AppDir $item) -Destination $StageDir -Recurse -Force
}

$issPath = Join-Path $AppDir "installer\Esyy_B1Connector.iss"
if (-not (Test-Path $issPath)) {
  throw "Script Inno Setup non trovato: $issPath"
}

$iscc = Resolve-IsccPath

Write-Host "Compilazione installer..."
Write-Host "ISCC: $iscc"
Write-Host "Payload: $StageDir"
Write-Host "Output: $OutAbs"

& $iscc `
  "/DAppVersion=$VersionSafe" `
  "/DSourceRoot=$StageDir" `
  "/DOutputRoot=$OutAbs" `
  $issPath

if ($LASTEXITCODE -ne 0) {
  throw "Compilazione installer fallita con exit code $LASTEXITCODE"
}

Write-Host "Installer creato in: $OutAbs"
