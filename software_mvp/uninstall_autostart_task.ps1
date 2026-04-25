Param(
  [string]$TaskName = "EsyyB1Connector"
)

$ErrorActionPreference = "Stop"

try {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
  Write-Host "Task '$TaskName' rimossa."
}
catch {
  Write-Host "Task '$TaskName' non trovata o gia rimossa."
}
