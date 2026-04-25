# Installer Windows - Esyy B1Connector

Guida rapida per creare e distribuire un installer `.exe` trasportabile.

## 1) Prerequisiti macchina build

- Windows
- Repository locale aggiornata
- Inno Setup 6 installato (`ISCC.exe`)

Download Inno Setup:

- `https://jrsoftware.org/isdl.php`

## 2) Generazione installer

Da PowerShell:

```powershell
cd "C:\Esyy Suite\esyy-B1Connector\software_mvp"
.\build_installer.ps1
```

Output:

- file setup in `software_mvp\dist\installer\`

## 3) Cosa contiene il setup

L'installer copia:

- applicazione `app\`
- script di avvio/setup
- file `.env.example`
- requirements Python

Non copia:

- `.venv` locale build
- `.env` con credenziali della macchina build
- DB locale/artefatti runtime

## 4) Cosa fa il setup lato cliente

Installazione tipica:

- cartella default: `C:\Program Files\Esyy\B1Connector`
- crea `.venv`
- installa dipendenze Python
- installa task scheduler `EsyyB1Connector`
- avvia app su `127.0.0.1:8010`

## 5) Primo avvio e verifica

```powershell
Invoke-WebRequest "http://127.0.0.1:8010/api/system/health" -UseBasicParsing
```

Se `status=ok`, aprire:

- `http://127.0.0.1:8010/login`

## 6) Autostart e gestione task

Nome task standard:

- `EsyyB1Connector`

Riavvio task:

```powershell
Stop-ScheduledTask -TaskName "EsyyB1Connector"
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName "EsyyB1Connector"
```

Rimozione autostart:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Program Files\Esyy\B1Connector\uninstall_autostart_task.ps1" -TaskName "EsyyB1Connector"
```

## 7) Log utili

- `C:\Program Files\Esyy\B1Connector\logs\uvicorn_out.log`
- `C:\Program Files\Esyy\B1Connector\logs\uvicorn_err.log`

## 8) Troubleshooting build installer

Errore `ISCC.exe non trovato`:

- installare Inno Setup 6 o verificare path:
  - `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`

Errore setup con permessi:

- eseguire setup come amministratore.
