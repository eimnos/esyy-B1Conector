# Proposta software installabile - SAP/SQL Server -> BigQuery -> Looker

## Obiettivo

Creare un applicativo installabile che permetta a te o al cliente finale di gestire in autonomia:

- configurazione connessioni SQL Server e BigQuery
- creazione/modifica viste SQL di reporting
- schedulazione frequenze di aggiornamento
- esportazione dati verso BigQuery
- permessi per utente/email (ACL Looker)
- monitoraggio run, errori e log

## Architettura consigliata (pragmatica)

Stack suggerito per velocita e robustezza:

- Backend: `Python + FastAPI`
- UI configurazione: `FastAPI + Jinja/HTMX` (web app leggera)
- Scheduler: `APScheduler` (job orari/giornalieri)
- DB configurazione locale: `SQLite` (poi `PostgreSQL` se multi-utente intenso)
- Connettori: `pyodbc` (SQL Server), `google-cloud-bigquery` (BigQuery)
- Logging: file + tabella DB (`run_log`)

Perche questa scelta:

- riusa subito il codice Python gia funzionante
- installazione semplice su Windows
- niente frontend complesso obbligatorio in fase 1
- facilmente estendibile a prodotto multi-cliente

## Moduli applicativi

1. `Config Manager`
- anagrafica tenant/clienti
- connessioni SQL Server e BigQuery
- test connessione

2. `View Manager`
- elenco viste SQL configurate
- editor SQL con versionamento
- azioni: `test query`, `create/replace view`, `rollback versione`

3. `Pipeline Manager`
- definizione pipeline: `view sorgente -> tabella BigQuery`
- mapping tipi e policy (`WRITE_TRUNCATE` / append in futuro)
- run manuale e run schedulato

4. `Scheduler`
- frequenze configurabili: ogni N minuti/ore, giornaliero, fasce orarie
- gestione pause/riavvio job

5. `ACL Manager`
- tabella mapping `user_email -> ov_codice_cliente`
- supporto master user con `__ALL__`
- import/export ACL da CSV

6. `Monitoring`
- stato ultimo run per pipeline
- righe estratte/caricate
- tempo esecuzione
- errore ultimo run
- log scaricabili

## Modello dati minimo (DB configurazione app)

Tabelle consigliate:

- `tenants`: cliente, stato, note
- `data_sources`: SQL Server connection metadata per tenant
- `report_views`: nome vista, SQL, versione, attiva
- `pipelines`: vista sorgente, tabella BigQuery target, policy write
- `schedules`: cron/frequenza, timezone, attiva
- `acl_rules`: user_email, customer_code, is_active
- `run_log`: pipeline_id, start/end, status, righe, messaggio errore
- `app_users`: utenti applicazione e ruoli (`admin`, `operator`, `viewer`)

## Flusso operativo utente finale

1. configura connessioni
2. crea o modifica una vista di reporting
3. collega la vista a una pipeline BigQuery
4. imposta frequenza aggiornamento
5. gestisce ACL utenti report
6. controlla dashboard stato job/log

## Installazione (fase 1)

Modalita semplice su Windows server:

- cartella app (`C:\VtronikBIApp`)
- virtualenv Python
- servizio Windows per backend/scheduler (NSSM o servizio nativo)
- backup giornaliero DB configurazione

Alternativa fase 2:

- Docker Compose (app + db) per deployment replicabile multi-cliente

## Sicurezza minima obbligatoria

- password connessioni cifrate a riposo (non in chiaro nei file)
- ruoli app separati (`admin`/`operator`)
- audit log modifiche configurazione
- niente account SQL `sa` in produzione (utente least privilege)

## Roadmap consigliata

Fase 1 (1-2 settimane):

- MVP installabile con config connessioni, pipeline, scheduler, log
- migrazione script export dentro app

Fase 2 (1 settimana):

- View Manager con versionamento SQL e rollback
- ACL Manager completo con `__ALL__`

Fase 3 (1 settimana):

- hardening sicurezza
- pacchetto installazione standard per nuovi clienti
- template onboarding nuovo tenant

## Prossima azione concreta

Avviare subito uno scaffold tecnico MVP con:

- struttura progetto FastAPI
- schema DB configurazione
- endpoint CRUD base (`views`, `pipelines`, `schedules`, `acl`)
- pagina web admin iniziale
