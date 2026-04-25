Param(
  [string]$Version = (Get-Date -Format "yyyyMMdd_HHmm"),
  [string]$OutputDir = ".\dist"
)

$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

$OutputDirAbs = Resolve-Path -Path $OutputDir -ErrorAction SilentlyContinue
if (-not $OutputDirAbs) {
  New-Item -ItemType Directory -Path $OutputDir | Out-Null
  $OutputDirAbs = Resolve-Path -Path $OutputDir
}

$PackageName = "vtronik_bi_mvp_$Version"
$StageDir = Join-Path $OutputDirAbs $PackageName
$ZipFile = Join-Path $OutputDirAbs "$PackageName.zip"

if (Test-Path $StageDir) {
  Remove-Item -Recurse -Force $StageDir
}
New-Item -ItemType Directory -Path $StageDir | Out-Null

$IncludePaths = @(
  "app",
  "requirements.txt",
  "README.md",
  ".env.example",
  "build_installer.ps1",
  "install_client.cmd",
  "installer",
  "run_prod.cmd",
  "run_prod.ps1",
  "run_dev.ps1",
  "setup_windows.ps1",
  "install_autostart_task.ps1",
  "uninstall_autostart_task.ps1"
)

foreach ($item in $IncludePaths) {
  Copy-Item -Path (Join-Path $AppDir $item) -Destination $StageDir -Recurse -Force
}

if (Test-Path $ZipFile) {
  Remove-Item -Force $ZipFile
}

Compress-Archive -Path (Join-Path $StageDir "*") -DestinationPath $ZipFile -Force

Write-Host "Pacchetto creato: $ZipFile"
