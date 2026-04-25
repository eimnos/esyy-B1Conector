Param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r .\requirements.txt

uvicorn app.main:app --reload --host $HostName --port $Port
