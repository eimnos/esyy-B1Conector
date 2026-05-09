param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8010,
    [switch]$StatusOnly,
    [switch]$NoStopExisting
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section([string]$Text) {
    Write-Host ""
    Write-Host "=== $Text ===" -ForegroundColor Cyan
}

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-AppPath {
    return (Join-Path (Get-RepoRoot) "software_mvp")
}

function Get-PythonExe([string]$AppPath) {
    $venvPy = Join-Path $AppPath ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
        return (Resolve-Path $venvPy).Path
    }
    throw "Python virtualenv non trovato: $venvPy. Esegui prima setup/install del progetto."
}

function Stop-UvicornProcesses([switch]$Skip) {
    if ($Skip) {
        return
    }
    $rows = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -like "*uvicorn app.main:app*"
    }
    foreach ($row in $rows) {
        try {
            Stop-Process -Id $row.ProcessId -Force -ErrorAction Stop
            Write-Host "Processo uvicorn terminato: PID $($row.ProcessId)"
        } catch {
            Write-Warning "Impossibile terminare PID $($row.ProcessId): $($_.Exception.Message)"
        }
    }
}

function Start-Uvicorn([string]$AppPath, [string]$PythonExe, [string]$HostName, [int]$Port) {
    $logsDir = Join-Path $AppPath "logs"
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir | Out-Null
    }

    $outLog = Join-Path $logsDir "collaudo_wizard_sap_b1_out.log"
    $errLog = Join-Path $logsDir "collaudo_wizard_sap_b1_err.log"
    Remove-Item $outLog, $errLog -ErrorAction SilentlyContinue

    Start-Process `
        -FilePath $PythonExe `
        -WorkingDirectory $AppPath `
        -ArgumentList @(
            "-m", "uvicorn", "app.main:app",
            "--host", $HostName,
            "--port", "$Port",
            "--log-level", "info"
        ) `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -WindowStyle Hidden | Out-Null

    Start-Sleep -Seconds 3

    $healthUrl = "http://$HostName`:$Port/api/system/health"
    try {
        $res = Invoke-WebRequest $healthUrl -UseBasicParsing -TimeoutSec 8
        if ($res.StatusCode -eq 200) {
            Write-Host "App avviata correttamente su $healthUrl" -ForegroundColor Green
            return
        }
        throw "Health endpoint status non valido: $($res.StatusCode)"
    } catch {
        Write-Warning "Health check fallito: $($_.Exception.Message)"
        if (Test-Path $errLog) {
            Write-Host ""
            Write-Host "Ultime righe errore:"
            Get-Content $errLog -Tail 40
        }
        throw "Avvio FastAPI non riuscito."
    }
}

function Show-Urls([string]$HostName, [int]$Port) {
    Write-Section "URL collaudo"
    $base = "http://$HostName`:$Port"
    Write-Host "$base/ui/wizard/sap"
    Write-Host "$base/ui/configurations"
    Write-Host "$base/ui/summaries"
    Write-Host "$base/api/system/health"
}

function Show-DbStatus([string]$AppPath, [string]$PythonExe) {
    Write-Section "Stato DB (output sicuro)"
    $script = @'
import os
import sys
import sqlite3

sys.path.insert(0, os.getcwd())
from app.config import settings

def parse_kv(conn_str: str) -> dict[str, str]:
    payload = {}
    for token in (conn_str or "").split(";"):
        chunk = token.strip()
        if not chunk or "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        payload[key.strip().upper()] = value.strip()
    return payload

def mask_server(value: str) -> str:
    clean = (value or "").strip()
    if not clean:
        return ""
    def mask_token(token: str) -> str:
        t = (token or "").strip()
        if not t:
            return ""
        if len(t) <= 4:
            return "*" * len(t)
        return t[:2] + "***" + t[-2:]
    if "\\" in clean:
        host, inst = clean.split("\\", 1)
        return f"{mask_token(host)}\\{mask_token(inst)}"
    if "," in clean:
        host, port = clean.rsplit(",", 1)
        return f"{mask_token(host)},{port}"
    return mask_token(clean)

def mask_database(value: str) -> str:
    clean = (value or "").strip()
    if not clean:
        return ""
    if len(clean) <= 4:
        return "*" * len(clean)
    return clean[:2] + "***" + clean[-2:]

def safe_print(msg: str, value: str):
    print(f"{msg}: {value}")

url = settings.app_db_url
if not url.startswith("sqlite:///"):
    safe_print("db_mode", "non-sqlite")
    safe_print("source_db_engine", "n/d")
    safe_print("sqlserver_conn_str", "n/d")
    safe_print("wizard_sap_status", "n/d")
    raise SystemExit(0)

db_path = url.replace("sqlite:///", "")
safe_print("sqlite_path", db_path)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

settings_rows = conn.execute(
    "SELECT key, value FROM app_settings WHERE key IN ('source_db_engine','sqlserver_conn_str','hana_conn_str')"
).fetchall()
settings_map = {row["key"]: row["value"] or "" for row in settings_rows}

source_db_engine = (settings_map.get("source_db_engine") or "").strip() or "(vuoto)"
sql_conn = settings_map.get("sqlserver_conn_str") or ""
hana_conn = settings_map.get("hana_conn_str") or ""

safe_print("source_db_engine", source_db_engine)
safe_print("sqlserver_conn_str", "presente" if sql_conn.strip() else "assente")
safe_print("hana_conn_str", "presente" if hana_conn.strip() else "assente")

if sql_conn.strip():
    kv = parse_kv(sql_conn)
    server = mask_server(kv.get("SERVER", ""))
    database = mask_database((kv.get("DATABASE", "") or "").strip())
    safe_print("sqlserver_server", server or "(n/d)")
    safe_print("sqlserver_database", database or "(n/d)")

if hana_conn.strip():
    kv = parse_kv(hana_conn)
    servernode = mask_server((kv.get("SERVERNODE", "") or "").strip())
    dbname = mask_database((kv.get("DATABASENAME", "") or "").strip())
    safe_print("hana_servernode", servernode or "(n/d)")
    safe_print("hana_database", dbname or "(n/d)")

rows = conn.execute(
    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='wizard_sessions'"
).fetchone()

if not rows:
    safe_print("wizard_sessions_table", "assente")
    safe_print(
        "wizard_sessions_hint",
        "Eseguire init_db() una volta per creare la tabella wizard_sessions.",
    )
else:
    safe_print("wizard_sessions_table", "presente")
    rows = conn.execute(
        """
        SELECT id, tenant_id, user_id, current_step_id, status, updated_at, completed_at
        FROM wizard_sessions
        WHERE wizard_id = 'sap'
        ORDER BY updated_at DESC, id DESC
        LIMIT 3
        """
    ).fetchall()

    if not rows:
        safe_print("wizard_sap_sessions", "nessuna")
    else:
        safe_print("wizard_sap_sessions", str(len(rows)))
        for row in rows:
            safe_print(
                "wizard_sap_row",
                (
                    f"id={row['id']} "
                    f"tenant={row['tenant_id']} "
                    f"user_id={row['user_id']} "
                    f"step={row['current_step_id']} "
                    f"status={row['status']} "
                    f"updated_at={row['updated_at']} "
                    f"completed_at={row['completed_at']}"
                ),
            )

conn.close()
'@

    $tmpPy = Join-Path $env:TEMP ("esyy_wizard_sap_status_" + $PID + ".py")
    try {
        Set-Content -Path $tmpPy -Value $script -Encoding UTF8
        & $PythonExe $tmpPy
    } finally {
        Remove-Item $tmpPy -ErrorAction SilentlyContinue
    }
}

function Run-PyCompile([string]$AppPath, [string]$PythonExe) {
    Write-Section "py_compile"
    & $PythonExe -m py_compile `
        (Join-Path $AppPath "app\main.py") `
        (Join-Path $AppPath "app\ui_routes.py") `
        (Join-Path $AppPath "app\models.py") `
        (Join-Path $AppPath "app\database.py") `
        (Join-Path $AppPath "app\services\wizard_definitions.py") `
        (Join-Path $AppPath "app\services\wizard_session_service.py")
    Write-Host "py_compile completato." -ForegroundColor Green
}

try {
    $appPath = Get-AppPath
    if (-not (Test-Path $appPath)) {
        throw "Cartella software_mvp non trovata: $appPath"
    }

    Set-Location $appPath
    $pythonExe = Get-PythonExe -AppPath $appPath

    if (-not $StatusOnly) {
        Run-PyCompile -AppPath $appPath -PythonExe $pythonExe
        Stop-UvicornProcesses -Skip:$NoStopExisting
        Start-Uvicorn -AppPath $appPath -PythonExe $pythonExe -HostName $HostName -Port $Port
    }

    Show-Urls -HostName $HostName -Port $Port
    Show-DbStatus -AppPath $appPath -PythonExe $pythonExe

    Write-Section "Note"
    Write-Host "- Nessuna password viene stampata."
    Write-Host "- La connection string completa non viene mai mostrata."
    Write-Host "- Per verificare la bozza: esegui il wizard SAP e poi rilancia con -StatusOnly."
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
