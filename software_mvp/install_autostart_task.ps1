Param(
  [string]$TaskName = "EsyyB1Connector",
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8010,
  [switch]$UseCurrentUser
)

$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunScript = Join-Path $AppDir "run_prod.cmd"

if (-not (Test-Path $RunScript)) {
  throw "Script non trovato: $RunScript"
}

$ActionArgs = "/c `"`"$RunScript`" $HostName $Port`""
$Action = New-ScheduledTaskAction `
  -Execute "cmd.exe" `
  -Argument $ActionArgs `
  -WorkingDirectory $AppDir

$Triggers = @(
  New-ScheduledTaskTrigger -AtStartup
)

$Settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 1)

if ($UseCurrentUser) {
  $CurrentUser = "$env:USERDOMAIN\$env:USERNAME"
  $Principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType InteractiveToken -RunLevel Highest
}
else {
  $Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
}

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Triggers `
  -Principal $Principal `
  -Settings $Settings `
  -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Host "Task '$TaskName' installata e avviata."
