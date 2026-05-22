# Software MVP configuratore BI

MVP installabile per gestire:

- viste SQL Server di reporting
- pipeline verso BigQuery
- scheduler run
- ACL email -> codice cliente (con supporto `__ALL__`)
- log esecuzioni

## Avvio rapido (Windows/PowerShell)

```powershell
cd "C:\Progetti clienti\Vtronik\BI\software_mvp"
copy .env.example .env
.\run_dev.ps1
```

Per avvio senza autoreload (modalita produzione locale):

```powershell
cd "C:\BigQuery\software_mvp"
.\run_prod.ps1
```

Alternativa senza PowerShell (cmd):

```cmd
cd /d C:\BigQuery\software_mvp
run_prod.cmd 127.0.0.1 8010
```

Apri:

- Login: `http://127.0.0.1:8010/login`
- Home: `http://127.0.0.1:8010/`
- API docs: `http://127.0.0.1:8010/docs`
- UI Views: `http://127.0.0.1:8010/ui/views`
- UI Pipelines: `http://127.0.0.1:8010/ui/pipelines`
- UI Schedules: `http://127.0.0.1:8010/ui/schedules`
- UI ACL: `http://127.0.0.1:8010/ui/acl`
- UI License: `http://127.0.0.1:8010/ui/license`
- UI Settings (solo admin): `http://127.0.0.1:8010/ui/settings`
- UI Users (solo admin): `http://127.0.0.1:8010/ui/users`

## Troubleshooting avvio

Se compare errore Windows `WinError 10013` su bind `0.0.0.0:8080`:

- avvia su localhost:
  - `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010`
- oppure cambia porta (es. `8010`):
  - `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010`
- se serve accesso da altri PC, usa `--host 0.0.0.0` su una porta consentita da policy/firewall.

Se il browser mostra "Impossibile raggiungere il sito" ma `health` locale risponde:

- il server potrebbe essere in ascolto su `127.0.0.1` (solo locale)
- per accesso da altri PC:
  1. avvia uvicorn con `--host 0.0.0.0 --port 8010`
  2. apri firewall Windows su porta 8010 (inbound TCP)
  3. usa URL `http://IP_DEL_SERVER:8010/login` dal PC client

Se compare errore `ModuleNotFoundError: No module named 'app'`:

- stai avviando `uvicorn` dalla cartella sbagliata
- soluzione 1:
  - `cd C:\BigQuery\software_mvp`
  - `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010`
- soluzione 2 (valida da qualunque path):
  - `C:\BigQuery\software_mvp\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir C:\BigQuery\software_mvp --host 127.0.0.1 --port 8010`

Se compare errore `Form data requires "python-multipart" to be installed`:

- installa dipendenza nel venv:
  - `C:\BigQuery\software_mvp\.venv\Scripts\python.exe -m pip install python-multipart==0.0.20`
- oppure riallinea tutto:
  - `C:\BigQuery\software_mvp\.venv\Scripts\python.exe -m pip install -r C:\BigQuery\software_mvp\requirements.txt`

Se compare errore `ModuleNotFoundError: No module named 'itsdangerous'`:

- e richiesta da `SessionMiddleware` (login/sessioni)
- installa:
  - `C:\BigQuery\software_mvp\.venv\Scripts\python.exe -m pip install itsdangerous==2.2.0`
- poi rilancia uvicorn

## Avvio automatico Windows (senza comando manuale)

Script inclusi:

- `install_client.cmd`: setup one-click per cliente (dipendenze + autostart)
- `setup_windows.ps1`: setup ambiente (.env, venv, dipendenze)
- `install_autostart_task.ps1`: installa task scheduler di auto-avvio
- `uninstall_autostart_task.ps1`: rimuove task scheduler
- `run_prod.cmd`: avvio server produzione con restart automatico (watchdog)
- `run_prod.ps1`: avvio produzione manuale (fallback)
- `build_installer.ps1`: genera installer `.exe` con Inno Setup
- `installer\Esyy_B1Connector.iss`: script installer Windows

Installazione one-click (consigliata):

```cmd
cd /d C:\BigQuery\software_mvp
install_client.cmd
```

Esempio installazione completa:

```powershell
cd "C:\BigQuery\software_mvp"
.\setup_windows.ps1 -InstallDeps -InstallAutostart -HostName 127.0.0.1 -Port 8010
```

Rimozione auto-avvio:

```powershell
cd "C:\BigQuery\software_mvp"
.\uninstall_autostart_task.ps1
```

Nota:

- il task usa di default nome `EsyyB1Connector`
- il task usa di default account `SYSTEM`
- puoi installarlo con utente corrente usando:
  - `.\install_autostart_task.ps1 -TaskName EsyyB1Connector -UseCurrentUser`
- il task avvia `run_prod.cmd`, che riavvia automaticamente uvicorn se il processo si chiude
- log runtime in `C:\BigQuery\software_mvp\logs\uvicorn_out.log` e `uvicorn_err.log`

## Configurazione minima

In `.env`:

- `APP_DB_URL`: DB di configurazione (default SQLite locale)
- `APP_SESSION_SECRET`: segreto sessione web (obbligatorio in produzione)
- `APP_ADMIN_USERNAME`: username admin bootstrap primo avvio
- `APP_ADMIN_PASSWORD`: password admin bootstrap primo avvio
- `SQLSERVER_CONN_STR`: connessione SQL Server (necessaria per publish view)
- `BQ_PROJECT_ID`: project GCP di default
- `BQ_DATASET`: dataset BigQuery di default
- `BQ_TABLE`: tabella BigQuery di default
- `BQ_LOCATION`: location BigQuery (`EU`, `US`, ...)
- `BQ_CREDENTIALS_FILE`: path locale JSON service account (se vuoto usa ADC)
- `PIPELINE_COMMAND_TIMEOUT_SECONDS`: timeout comando pipeline
- `ESYY_PRODUCT_CODE`: codice prodotto locale (default `esyy-b1-connector`)
- `ESYY_LICENSE_MODE`: modalita licensing (`open_trial`, `local_file`, `portal`)
- `ESYY_LICENSE_PORTAL_URL`: URL portale Esyy (futuro, opzionale)
- `ESYY_LICENSE_CHECK_TIMEOUT_SECONDS`: timeout check remoto futuro
- `ESYY_LICENSE_GRACE_DAYS`: grace period previsto per enforcement futuro
- `ESYY_LICENSE_FILE`: path file licenza locale (modo `local_file`)

Nota `APP_DB_URL`:

- se lasci `sqlite:///./configurator.db`, l'app lo normalizza automaticamente su
  `C:\BigQuery\software_mvp\configurator.db` (cartella applicazione), evitando drift dati dovuti alla working directory.

## Licensing (fase attuale: non bloccante)

- Pagina UI: `/ui/license`
- Endpoint API:
  - `GET /api/license/status`
  - `POST /api/license/activate-open-trial`
  - `POST /api/license/check`
  - `POST /api/license/reset-local`

Comportamento attuale:

- modalita di default `open_trial`
- nessun blocco funzionale applicato
- tutte le features risultano abilitate
- app pienamente utilizzabile anche offline

Comportamento futuro previsto:

- integrazione con portale Esyy in modalita `portal`
- eventuale file licenza locale in modalita `local_file`
- possibile enforcement via `should_block_app` (oggi sempre `False`)

## Ruoli e accessi

- `admin`: accesso completo, inclusa gestione utenti e ACL write
- `operator`: gestione operativa (views, pipelines, schedules, run), ACL sola lettura
- `viewer`: sola lettura pagine UI

Al primo avvio, se non esistono utenti nel DB configurazione, viene creato automaticamente un admin con:

- username: `APP_ADMIN_USERNAME`
- password: `APP_ADMIN_PASSWORD`

Dopo il primo login, cambia subito la password da `UI Users`.

## Configurazione SQL Server da UI

Per evitare modifiche manuali al file `.env` puoi configurare la connessione SQL Server da:

- `UI Settings` -> `Impostazioni SQL Server`
- `UI Settings` -> `Wizard Connection String`

Comportamento:

- se in `Settings` e presente una stringa connessione, `Publish View` usa quella
- se in `Settings` il valore e vuoto, `Publish View` usa il fallback `SQLSERVER_CONN_STR` da `.env`
- nella stessa pagina e disponibile il pulsante `Test connessione`

Formato tipico SQL Server:

- `DRIVER={ODBC Driver 17 for SQL Server};SERVER=HOST\\ISTANZA;DATABASE=DB;UID=utente;PWD=password;Encrypt=no;TrustServerCertificate=yes;`
- oppure con porta:
  - `DRIVER={ODBC Driver 17 for SQL Server};SERVER=HOST,1433;DATABASE=DB;UID=utente;PWD=password;Encrypt=yes;TrustServerCertificate=yes;`

## Configurazione BigQuery da UI

In `UI Settings` trovi una sezione BigQuery con:

- salvataggio parametri runtime (`project`, `dataset`, `table`, `location`, `credentials file`)
- `Test connessione BigQuery`
- `Crea/valida dataset BigQuery` (bootstrap dataset)

Note input utili:

- campo `dataset`: puoi inserire sia solo dataset (`sap_reporting`) sia `project.dataset`
- campo `table` in pipeline: puoi inserire `table`, `dataset.table` o `project.dataset.table`

La priorita configurazione e:

1. valori salvati in app (tabella `app_settings`)
2. fallback valori da `.env`

## SAP HANA (preparazione)

La pagina `UI Settings` include anche un wizard HANA per generare e salvare la stringa connessione.

Formato tipico HANA:

- `DRIVER={HDBODBC};SERVERNODE=hana-host:30015;UID=SYSTEM;PWD=***;ENCRYPT=TRUE;DATABASENAME=DB;`

Nota:

- al momento `Publish View` e la modalita managed pipeline sono ottimizzati per SQL Server.
- la configurazione HANA e stata introdotta per preparare l'estensione multi-db.

## Flusso base consigliato

1. Crea una `view` da UI (`/ui/views`).
2. Apri il dettaglio view e fai publish su SQL Server.
3. Configura BigQuery da `UI Settings`.
4. Crea una `pipeline` da UI (`/ui/pipelines`) con `source_view_id`.
5. Per run:
   - `command` valorizzato: esegue comando custom
   - `command` vuoto: usa modalita managed (`select_sql` view -> load BigQuery)
6. Crea `schedule` con cron (`/ui/schedules`), ad esempio `0 */2 * * *`.
7. Gestisci ACL (`/ui/acl`) per utenti report e master `__ALL__`.

## Note

- Scheduler usa `APScheduler` con cron standard a 5 campi.
- Le pipeline eseguono il campo `command` quando valorizzato.
- Se `command` e vuoto, la pipeline usa la modalita managed (`SQL Server -> BigQuery`) e richiede `source_view_id`.

## Distribuzione portabile per clienti

Per creare un pacchetto zip portabile:

```powershell
cd "C:\Progetti clienti\Vtronik\BI\software_mvp"
.\package_release.ps1
```

Output:

- zip in `.\dist\` con app, script setup/avvio, template `.env.example`

### Installer `.exe` (consigliato per portabilita clienti)

Prerequisito build:

- Inno Setup 6 installato (ISCC.exe)

Generazione installer:

```powershell
cd "C:\Esyy Suite\esyy-B1Connector\software_mvp"
.\build_installer.ps1
```

Output:

- setup in `.\dist\installer\`
- installazione guidata in `C:\Program Files\Esyy\B1Connector`

Durante il setup:

- crea ambiente Python (.venv)
- installa dipendenze
- installa task scheduler `EsyyB1Connector` (SYSTEM o utente corrente)
- apre il browser su `http://127.0.0.1:8010/login`

### Personalizzazione icona Windows

L'installer usa l'icona:

- `installer\assets\esyy_b1connector.ico`

Questa icona viene applicata a:

- file `Setup.exe`
- voce Programmi/Disinstalla (UninstallDisplayIcon)
- collegamenti Start Menu e Desktop creati dal setup
