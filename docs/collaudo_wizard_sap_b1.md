# Collaudo operativo Wizard SAP B1

## Obiettivo
Validare in ambiente reale che il wizard SAP B1:
- salvi solo bozza durante gli step intermedi
- applichi i settings reali solo alla conferma finale
- aggiorni correttamente `wizard_sessions` e le pagine UI.

## Prerequisiti
- Ambiente operativo con accesso reale a SQL Server SAP B1.
- Driver ODBC SQL Server installato.
- Progetto disponibile in `C:\Esyy Suite\esyy-B1Connector`.
- Virtualenv `.venv` gia presente in `software_mvp` (oppure installazione gia fatta).

## Script di supporto
Usare:
- [scripts/collaudo_wizard_sap_b1.ps1](C:\Esyy Suite\esyy-B1Connector\scripts\collaudo_wizard_sap_b1.ps1)

Lo script:
- esegue `py_compile`
- avvia FastAPI su `127.0.0.1:8010`
- mostra URL utili
- stampa stato sintetico DB (senza password e senza connection string completa).

## 1) Avvio collaudo
Da PowerShell:

```powershell
cd "C:\Esyy Suite\esyy-B1Connector"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\collaudo_wizard_sap_b1.ps1"
```

Aprire poi:
- `http://127.0.0.1:8010/ui/wizard/sap`
- `http://127.0.0.1:8010/ui/configurations`
- `http://127.0.0.1:8010/ui/summaries`

## 2) Baseline stato DB (prima del wizard)
Eseguire:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\collaudo_wizard_sap_b1.ps1" -StatusOnly
```

Annotare:
- `source_db_engine`
- `sqlserver_conn_str`: presente/non presente
- `sqlserver_server` / `sqlserver_database` (se disponibili)
- stato `wizard_sessions` per `wizard_id=sap`.

## 3) Compilazione wizard SAP (bozza)
Nella UI `/ui/wizard/sap`:
1. Step Introduzione: `Conferma e continua`
2. Step Motore database: selezionare `SQL Server`
3. Step Server e database: inserire valori reali (host/istanza e DB SAP)
4. Step Credenziali: inserire utente tecnico SQL
5. Premere `Salva bozza` (prima della conferma finale)

## 4) Verifica: bozza non deve applicare settings reali
Rieseguire:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\collaudo_wizard_sap_b1.ps1" -StatusOnly
```

Atteso:
- `wizard_sessions` aggiornato (step corrente avanzato, stato in corso)
- `app_settings` **non ancora applicato** dal wizard finale
  - nessuna modifica definitiva nuova dovuta alla sola bozza.

Nota:
- Se erano gia presenti valori in `app_settings`, devono restare invariati dopo sola bozza.

## 5) Test connessione e conferma finale
Tornare sul wizard:
1. Step Test connessione: impostare esito `OK` (dopo verifica reale SQL Server)
2. Step Review: `Conferma finale`

Atteso in caso di successo:
- messaggio di completamento wizard SAP con apply settings.

Atteso in caso di errore:
- messaggio `Conferma finale non completata: ...`
- stato wizard non completato (`test_failed` o `in_progress`).

## 6) Verifiche post-conferma
Rieseguire:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\collaudo_wizard_sap_b1.ps1" -StatusOnly
```

Controllare:
- `source_db_engine = sqlserver`
- `sqlserver_conn_str`: presente
- `sqlserver_server` e `sqlserver_database` valorizzati (mascherati in output sicuro)
- `wizard_sessions` per `sap` con `status = completed`.

## 7) Verifiche UI finali
1. `/ui/configurations`:
   - card SAP con stato `Completato`
   - progress `100%`.
2. `/ui/summaries`:
   - stato SAP `Completato`
   - azione `Modifica con wizard` verso `/ui/wizard/sap`.

## Comandi utili
Stato rapido DB:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\collaudo_wizard_sap_b1.ps1" -StatusOnly
```

Avvio su porta diversa:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\collaudo_wizard_sap_b1.ps1" -Port 8011
```

## Sicurezza output
La procedura/script:
- non stampa password
- non stampa connection string completa
- mostra solo presenza stringa e campi non sensibili (`server`, `database`) se disponibili.
