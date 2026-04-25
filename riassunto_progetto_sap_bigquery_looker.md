# Riassunto dettagliato del progetto SAP Business One → BigQuery → Looker Studio

## Obiettivo iniziale

L’obiettivo era collegare i dati di SAP Business One, che gira su SQL Server on-premise, a Looker Studio per mostrare a un cliente esterno lo stato di produzione e spedizione dei propri ordini.

All’inizio sono state valutate due strade:

- collegamento diretto di Looker Studio a SQL Server
- passaggio intermedio tramite BigQuery

Dopo le verifiche tecniche, è stata scelta la seconda strada, perché è molto più prudente per un gestionale di produzione.

---

## 1) Analisi iniziale dell’infrastruttura

È stato verificato che:

- usi **SAP Business One 10**
- il database è su **SQL Server on-premise**
- hai **una sola company**
- il server SQL è una **named instance**:
  `WIN-NSICHQOT7RV\MSSQL2019`
- il firewall interno è **pfSense**
- a monte c’è un router TIM

Dagli screenshot è stata ricostruita la situazione di rete:

- pfSense WAN: `192.168.0.100`
- router TIM LAN gateway: `192.168.0.1`
- router TIM WAN pubblico: `95.230.103.10`

### Conclusione della verifica rete

- **non sei in CGNAT**
- sei in **doppio NAT**
- il collegamento diretto a SQL Server sarebbe stato teoricamente possibile
- però avrebbe richiesto pubblicazione del DB su internet, NAT, whitelist e modifica impostazioni lato SQL/network

Dato che hai espresso la necessità di **non toccare troppo il DB del gestionale**, è stata esclusa come soluzione consigliata la connessione diretta da Looker Studio a SQL Server.

---

## 2) Scelta dell’architettura finale

È stata definita questa architettura:

**SQL Server interno → view dedicata → script Python locale → BigQuery → Looker Studio**

Questa scelta ha questi vantaggi:

- il DB SAP resta interno
- non esponi SQL Server su internet
- il dataset per il cliente è separato e pulito
- Looker Studio legge da BigQuery, non dal gestionale
- puoi aggiornare i dati con frequenza controllata

---

## 3) Revisione della query SAP

È stata condivisa la query iniziale usata dentro SAP, basata su:

- `OWOR` per ordini di produzione
- `ORDR` / `RDR1` per ordini cliente
- `DLN1` per DDT
- `OSCN` per codici articolo cliente

È stato discusso il fatto che vuoi **escludere i documenti chiusi**, per evitare che il dataset cresca continuamente nel tempo.

La query è stata quindi riscritta con questi obiettivi:

- mantenere solo le righe ordine **aperte**
- continuare a calcolare le quantità consegnate
- aggiungere campi utili per il report cliente
- usare alias compatibili con BigQuery / Looker Studio

La query finale è stata riscritta con campi come:

- `wo_entry`
- `wo_numero`
- `ov_entry`
- `ov_numero`
- `wo_data_fine_produzione`
- `ov_data_consegna`
- `ov_codice_articolo_cliente`
- `ov_quantita_ordinata`
- `wo_quantita_pianificata`
- `wo_quantita_completata`
- `ddt_quantita_consegnata`
- `ddt_quantita_residua`
- `stato_produzione`
- `stato_spedizione`

---

## 4) Creazione della view SQL Server

Dopo aver consolidato la query, è stato deciso di non leggere direttamente le tabelle SAP nello script ma di creare una **view SQL dedicata**.

È stata creata correttamente la view:

```text
 dbo.vw_reporting_stato_ordini_cliente
```

La view è stata:

- creata in SQL Server
- testata
- verificata come funzionante

Questo è stato un passaggio molto importante perché ha separato la logica di reporting dalla struttura operativa del gestionale.

---

## 5) Creazione del progetto Google Cloud

È stato creato il progetto Google Cloud:

```text
vtronik-sap-reporting-cliente
```

Poi sono state completate queste attività:

- abilitazione della **BigQuery API**
- creazione del dataset BigQuery:

```text
sap_reporting
```

A quel punto la parte cloud era pronta per ricevere i dati.

---

## 6) Service account e chiave JSON

È stato creato il service account per permettere allo script locale di scrivere su BigQuery.

È poi stato generato il file JSON della chiave e salvato in:

```text
C:\BigQuery\vtronik-sap-reporting-cliente-72be47a65bcb.json
```

Questa chiave è quella usata dallo script Python per autenticarsi su BigQuery.

---

## 7) Preparazione del PC interno

Sul PC interno che deve eseguire l’export è stata fatta tutta la parte di setup.

### Problema iniziale

Python sembrava installato, ma i comandi:

- `python`
- `py`

non erano riconosciuti dal prompt.

È stato verificato il percorso reale dell’eseguibile Python con:

```python
import sys
print(sys.executable)
```

ottenendo:

```text
C:\Users\datalab2\AppData\Local\Python\pythoncore-3.14-64\python.exe
```

Da quel momento è stato usato sempre quel percorso completo per eseguire Python.

### Installazione pacchetti

Sono stati installati correttamente:

- `pandas`
- `pyodbc`
- `google-cloud-bigquery`
- `pyarrow`

In seguito è stato anche suggerito `pandas-gbq`, ma non era necessario per arrivare al primo caricamento funzionante.

---

## 8) Verifica driver ODBC SQL Server

È stato verificato che il PC vedeva questi driver SQL Server:

- `ODBC Driver 17 for SQL Server`
- altri driver legacy e componenti aggiuntivi

Quindi è stato deciso di usare nello script:

```text
ODBC Driver 17 for SQL Server
```

senza dover installare il driver 18.

---

## 9) Primo sviluppo dello script Python

È stato costruito uno script Python che esegue queste operazioni:

1. connessione a SQL Server
2. lettura della view
3. trasformazione tipi colonne
4. autenticazione BigQuery tramite file JSON
5. caricamento nella tabella BigQuery
6. sovrascrittura completa del dataset a ogni esecuzione

La tabella BigQuery di destinazione è:

```text
vtronik-sap-reporting-cliente.sap_reporting.stato_ordini_cliente
```

---

## 10) Problema di autenticazione SQL Server

Il primo tentativo di esecuzione falliva con questo problema:

- lo script stava usando `Trusted_Connection=yes`
- SQL Server tentava di autenticare l’utente Windows:
  `V-TRONIK\datalab2`
- il login veniva rifiutato

È stato poi chiarito che l’accesso al database SAP avviene tramite:

- utente SQL Server: `sa`
- password nota

Lo script è stato quindi modificato per usare autenticazione SQL classica con:

- `UID=sa`
- `PWD=...`

ed è stata abbandonata la Windows authentication.

Questo ha risolto la parte di accesso a SQL Server.

---

## 11) Problemi di conversione tipi verso BigQuery

Una volta risolta la connessione SQL, lo script ha iniziato a leggere correttamente la view, ma ha avuto vari problemi nel caricamento su BigQuery.

### Primo problema

Le colonne numeriche erano state inizialmente mappate come `NUMERIC` in BigQuery, ma i dati arrivavano da pandas/pyarrow in modo non coerente.

Errore ottenuto:

- mismatch sui tipi numerici
- `ArrowInvalid`

### Soluzione

Le quantità sono state cambiate da `NUMERIC` a `FLOAT64`.

### Secondo problema

Successivamente lo script convertiva in stringa anche colonne che dovevano restare intere, come:

- `wo_entry`
- `wo_numero`
- `ov_entry`
- `ov_numero`

Errore ottenuto:

- valore stringa tipo `'1493'` non convertibile in `INT64`

### Soluzione

Le colonne sono state separate esplicitamente in gruppi:

- `DATE_COLUMNS`
- `INT_COLUMNS`
- `FLOAT_COLUMNS`
- `STRING_COLUMNS`

Per ciascun gruppo è stata applicata una conversione coerente.

### Terzo problema

Si è verificato anche un errore di indentazione Python durante un copia/incolla del blocco tipi.

### Soluzione

Lo script completo è stato riscritto da zero in versione coerente e già corretta.

---

## 12) Script finale funzionante

Lo script finale:

- si collega a SQL Server con `sa`
- legge la view `dbo.vw_reporting_stato_ordini_cliente`
- normalizza i tipi correttamente
- si autentica verso BigQuery con il file JSON
- carica i dati nella tabella BigQuery
- usa `WRITE_TRUNCATE`, quindi a ogni esecuzione **sostituisce** i dati precedenti

### Percorsi principali

```text
Script Python:
C:\BigQuery\scripts\export_sap_to_bigquery.py

Python:
C:\Users\datalab2\AppData\Local\Python\pythoncore-3.14-64\python.exe

Chiave JSON:
C:\BigQuery\vtronik-sap-reporting-cliente-72be47a65bcb.json
```

---

## 13) Primo caricamento riuscito

L’ultimo run andato a buon fine ha prodotto:

- connessione SQL Server: ok
- lettura view: ok
- righe estratte: **141**
- caricamento BigQuery: ok
- righe in tabella BigQuery: **141**

Quindi oggi il flusso dati è **operativo**.

---

## 14) Stato attuale del progetto

Ad oggi sono già stati completati con successo:

### Lato SQL Server / SAP

- query definita
- query migliorata
- view SQL creata
- view testata
- accesso SQL via `sa` funzionante

### Lato Google Cloud

- progetto creato
- BigQuery API abilitata
- dataset creato
- service account creato
- chiave JSON generata

### Lato PC interno

- Python installato
- pacchetti necessari installati
- driver ODBC verificato
- script Python funzionante
- primo caricamento BigQuery completato

---

## 15) Problema residuo su Looker Studio

Quando hai iniziato a collegare la tabella a Looker Studio è comparso questo errore:

- confronto non valido tra `DATE` e `FLOAT64`

### Interpretazione

Looker Studio stava usando un campo numerico come campo data in un filtro o date range.

La spiegazione più probabile è che:

- il **Date range dimension** del report o della sorgente dati non era impostato correttamente
- oppure Looker Studio aveva memorizzato tipi campo non aggiornati

### Soluzione individuata

- verificare i tipi dei campi data nella sorgente
- impostare come campo data uno dei campi corretti, ad esempio:
  - `ov_data_ordine`
  - `ov_data_consegna`
  - `wo_data_inizio_produzione`
  - `wo_data_fine_produzione`
- se necessario fare **Reconnect** della sorgente dati, non solo refresh

Questa parte non è ancora stata completata, ma il problema è stato isolato.

---

## 16) Schedulazione dello script

È stato spiegato come schedulare lo script tramite **Utilità di pianificazione di Windows**, creando un’attività con:

- nome: `Export SAP verso BigQuery`
- esecuzione anche senza utente loggato
- privilegi elevati
- trigger 2 volte al giorno oppure ogni ora
- programma/script = Python
- argomento = script `.py`
- cartella iniziale = `C:\BigQuery\scripts`

È stata anche consigliata una soluzione migliore:

### usare un file `.bat` con log

Percorso suggerito:

```text
C:\BigQuery\scripts\run_export_sap_to_bigquery.bat
```

Contenuto suggerito:

```bat
@echo off
echo ======================================== >> C:\BigQuery\scripts\export_log.txt
echo Avvio export %date% %time% >> C:\BigQuery\scripts\export_log.txt
"C:\Users\datalab2\AppData\Local\Python\pythoncore-3.14-64\python.exe" C:\BigQuery\scripts\export_sap_to_bigquery.py >> C:\BigQuery\scripts\export_log.txt 2>&1
echo Fine export %date% %time% >> C:\BigQuery\scripts\export_log.txt
```

Questo punto è stato spiegato, ma non è ancora stata verificata insieme la creazione effettiva dell’attività pianificata.

---

## 17) Raccomandazioni operative emerse

Durante il lavoro sono emerse alcune raccomandazioni importanti:

### 1. Non usare in produzione `sa`

Per i test va bene, ma per un flusso stabile sarebbe meglio creare un utente SQL dedicato, con accesso solo alla view.

### 2. Tenere il dataset “snello”

È stata scelta correttamente l’esclusione dei documenti chiusi, così la tabella non cresce all’infinito.

### 3. Sovrascrivere il dataset a ogni run

È il modello più semplice e pulito per questo caso, visto che interessa una fotografia attuale degli ordini aperti.

### 4. Partire con due aggiornamenti al giorno

Per iniziare è stato suggerito:

- mattina
- sera

Poi, se tutto è stabile, passare a refresh orario.

---

## 18) Situazione finale, in una riga

In questo momento è già stata realizzata con successo la pipeline:

**SAP SQL Server → view dedicata → script Python locale → BigQuery**

Restano da completare solo:

- sistemazione finale del report in **Looker Studio**
- eventuale **schedulazione automatica** dello script
- eventuale creazione di un **utente SQL dedicato** al posto di `sa`

---

## Riferimenti tecnici concreti usati

### File principali

```text
View SQL:
dbo.vw_reporting_stato_ordini_cliente

Script Python:
C:\BigQuery\scripts\export_sap_to_bigquery.py

Chiave JSON:
C:\BigQuery\vtronik-sap-reporting-cliente-72be47a65bcb.json

Python:
C:\Users\datalab2\AppData\Local\Python\pythoncore-3.14-64\python.exe
```

### Oggetti BigQuery

```text
Project:
vtronik-sap-reporting-cliente

Dataset:
sap_reporting

Tabella:
stato_ordini_cliente
```

---

## 19) Registro operativo continuo (dal 2026-04-11)

Da questa data il file viene mantenuto aggiornato a ogni attivita svolta nel progetto.

### 2026-04-11 - Setup tracciamento in questa cartella

- confermato workspace operativo: `C:\Progetti clienti\Vtronik\BI`
- confermata presenza file di riepilogo: `riassunto_progetto_sap_bigquery_looker.md`
- confermata presenza script operativo: `scripts\export_sap_to_bigquery.py`
- confermata presenza chiave service account locale: `vtronik-sap-reporting-cliente-72be47a65bcb.json`
- definita regola di lavoro: aggiornare questo file a ogni nuova attivita o modifica richiesta

### 2026-04-11 - Procedura controllo aggiornamento BigQuery

Per verificare se la tabella e stata aggiornata in settimana sono stati fissati questi controlli:

- controllo metadato tabella su BigQuery (`last_modified_time`)
- controllo job di caricamento (`LOAD`) su `region-eu.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
- controllo contenuto dati con `MAX()` sui campi data principali

Riferimento tabella:

- `vtronik-sap-reporting-cliente.sap_reporting.stato_ordini_cliente`

### 2026-04-11 - Automazione controllo freschezza (alert > 24h)

Sono stati creati nuovi file in `scripts`:

- `check_bigquery_freshness.py`
- `run_check_bigquery_freshness.bat`

Funzionamento implementato:

- legge l'ultimo job `LOAD` su `region-eu.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
- verifica stato job ed eventuale errore
- calcola ore trascorse dall'ultimo caricamento
- genera `[ALERT]` se l'ultimo `LOAD` supera 24 ore (exit code `2`)
- genera `[OK]` se aggiornamento entro soglia (exit code `0`)
- stampa anche metadati tabella e `MAX()` date business per diagnostica

Note tecniche:

- fallback automatico chiave JSON: prima `C:\BigQuery\...json`, poi file omonimo nella root progetto
- launcher `.bat` con logging su `scripts\bigquery_freshness_log.txt`

Verifica locale in questa sessione:

- sintassi Python script: OK (`py_compile`)
- esecuzione reale non testata qui per dipendenza mancante: `ModuleNotFoundError: No module named 'google'`

### 2026-04-11 - Chiarimento ambiente operativo

- questo PC (workspace `C:\Progetti clienti\Vtronik\BI`) viene usato solo per preparazione file e documentazione
- verifiche di funzionamento runtime da eseguire solo sul PC di produzione
- cartella di produzione confermata: `C:\BigQuery`

### 2026-04-11 - Comandi operativi per PC produzione (`C:\BigQuery`)

Comandi condivisi per eseguire gli script dal server operativo:

- installazione dipendenze BigQuery (se mancanti)
- esecuzione export verso BigQuery
- esecuzione controllo freschezza con soglia 24 ore
- lettura log dei controlli automatici

Percorsi operativi considerati:

- `C:\BigQuery\scripts\export_sap_to_bigquery.py`
- `C:\BigQuery\scripts\check_bigquery_freshness.py`
- `C:\BigQuery\scripts\run_check_bigquery_freshness.bat`

### 2026-04-11 - Esito primo test in produzione e fix

Output ricevuto dal PC produzione:

- export SAP -> BigQuery completato con successo
- righe caricate in tabella: `114`
- controllo freschezza fallito per permesso mancante su `region-eu.INFORMATION_SCHEMA.JOBS_BY_PROJECT` (errore `403 Access Denied`)

Correzioni applicate ai file sorgente in questa cartella di lavoro:

- `check_bigquery_freshness.py` aggiornato con fallback automatico:
  - se manca accesso a `JOBS_BY_PROJECT`, usa `last_modified_time` tabella come riferimento di freschezza
  - mantiene comunque output `[OK]/[ALERT]` con stessa soglia ore
- `run_check_bigquery_freshness.bat` aggiornato per loggare sempre correttamente `ExitCode`

Azione operativa richiesta:

- ricopiare in `C:\BigQuery\scripts` i due file aggiornati
- rilanciare il controllo freschezza dal PC produzione

### 2026-04-11 - Esito secondo test produzione (post-fallback)

Output ricevuto dopo rilancio su PC produzione:

- controllo eseguito con fallback attivo (permesso `JOBS_BY_PROJECT` ancora assente)
- stato controllo: `[OK] Frequenza aggiornamento nei limiti della soglia`
- metadato tabella rilevato: `2026-04-11 10:05:00` (Europe/Rome)
- righe in tabella: `114`
- max date dati lette correttamente:
  - `ov_data_ordine = 2026-03-31`
  - `ov_data_consegna = 2026-04-17`
  - `wo_data_fine_produzione = 2026-04-17`

Anomalia residua log:

- nel file `bigquery_freshness_log.txt` il campo `ExitCode` risultava ancora vuoto

Fix applicato:

- aggiornato `run_check_bigquery_freshness.bat` con `EnableDelayedExpansion`
- valorizzazione `EXIT_CODE` tramite `!ERRORLEVEL!`
- fallback difensivo a `1` se variabile vuota

### 2026-04-11 - Verifica finale fix ExitCode (produzione)

Eseguito in produzione:

- `cmd /c "C:\BigQuery\scripts\run_check_bigquery_freshness.bat"`
- controllo codice di uscita con `$LASTEXITCODE`

Risultato:

- `$LASTEXITCODE = 0`
- log con riga finale corretta: `ExitCode=0`
- controllo freschezza in stato `[OK]` con fallback su `last_modified_time` (permesso `JOBS_BY_PROJECT` non ancora assegnato)

Conclusione operativa:

- monitoraggio attivo e funzionante anche senza accesso a `INFORMATION_SCHEMA.JOBS_BY_PROJECT`
- i vecchi log con `ExitCode=` vuoto restano storici e non impattano il funzionamento corrente

### 2026-04-11 - Verifica rischio superamento BigQuery Free Tier

Indicazioni operative definite:

- Free Tier BigQuery da monitorare ogni mese:
  - storage: primi `10 GiB/mese` gratuiti
  - query analysis on-demand: primi `1 TiB/mese` gratuiti
- il caricamento batch (load job) usato dallo script di export non genera costo query analysis; restano eventuali costi storage oltre soglia

Controlli consigliati:

- controllo storage attuale dataset/tabella tramite `region-eu.INFORMATION_SCHEMA.TABLE_STORAGE`
- controllo bytes query mensili tramite `region-eu.INFORMATION_SCHEMA.JOBS_BY_PROJECT` (quando disponibile permesso)
- in alternativa, controllo da Cloud Billing Reports filtrando servizio BigQuery e SKUs

Valutazione preliminare sul caso corrente:

- con tabella attuale intorno a `114` righe il rischio di superare il limite storage gratuito appare molto basso
- il rischio principale (se mai) e sul volume query generate da Looker Studio nel mese, da verificare con metrica `total_bytes_billed`

### 2026-04-11 - Strategia sicurezza dati per utente Looker Studio

Nuovo requisito discusso:

- ogni utente Looker Studio deve vedere solo i dati del proprio `ov_codice_cliente`
- mappatura desiderata: `email_utente` -> `ov_codice_cliente`

Approccio consigliato:

- creare tabella ACL in BigQuery (es. `sap_reporting.acl_utenti_clienti`) con mapping email/codice cliente
- usare data source Looker Studio basata su query che unisce tabella dati + ACL e filtra con `@DS_USER_EMAIL`
- alternativa equivalente: esporre campo email derivato e attivare `Filter by email` nella data source

Punti operativi importanti:

- supporto many-to-many naturale (un utente puo vedere piu codici cliente e un codice puo essere visto da piu utenti)
- utenti devono consentire uso email in Looker Studio per row-level filtering
- attenzione al case delle email (normalizzare con `LOWER`)

### 2026-04-11 - Evoluzione verso soluzione rivendibile

Valutazione architetturale:

- fattibile trasformare il progetto in prodotto multi-cliente con pannello di configurazione
- configurazioni candidate: mapping ACL utenti/clienti, gestione viste sorgente, schedulazione export, stato run e log
- modello consigliato: piattaforma config-driven con metadati per tenant, evitando script hardcoded per singolo cliente

### 2026-04-11 - Deliverable SQL ACL Looker Studio

Creati i file per implementare subito il filtro per email utente:

- `sql\looker_acl_setup.sql`
- `sql\looker_acl_operativa.md`

Contenuto implementato:

- creazione tabella ACL `sap_reporting.acl_utenti_clienti`
- esempi di insert e query `MERGE` per manutenzione
- query finale Looker Studio con parametro `@DS_USER_EMAIL`
- query di validazione accessi e audit mapping

Prossimo step concordato:

- dopo attivazione ACL, avviare disegno di software installabile completo per gestione configurazioni multi-cliente

### 2026-04-11 - Fix sintassi BigQuery su script ACL

Errore rilevato in esecuzione SQL:

- `Syntax error: Expected ")" or "," but got keyword DEFAULT`

Correzione applicata su `sql\looker_acl_setup.sql`:

- rimosse clausole `DEFAULT` dalla `CREATE TABLE` (compatibilita maggiore)
- aggiunto `#standardSQL` in testa script
- aggiornato `INSERT` di esempio con valorizzazione esplicita di:
  - `is_active`
  - `created_at`
  - `updated_at`

### 2026-04-11 - Chiarimento parametro `@DS_USER_EMAIL`

Errore rilevato:

- `Query parameter 'DS_USER_EMAIL' not found`

Causa:

- `@DS_USER_EMAIL` e un parametro disponibile solo in Looker Studio (Custom Query del data source), non nella console SQL BigQuery.

Correzione applicata:

- in `sql\looker_acl_setup.sql` la query Looker con `@DS_USER_EMAIL` e stata lasciata come blocco commentato/copiabile
- script BigQuery ora eseguibile end-to-end senza errori di parametro

### 2026-04-11 - Dove eseguire la query ACL in Looker Studio

Richiesto chiarimento operativo su dove incollare la query con `@DS_USER_EMAIL`.

Percorso documentato:

- `Risorsa` -> `Gestisci origini dati aggiunte` -> `Aggiungi un'origine dati` -> `BigQuery` -> `Query personalizzata`
- alternativa su source esistente: `Risorsa` -> `Gestisci origini dati aggiunte` -> `Modifica` -> `Modifica connessione` -> `Query personalizzata`

Riferimento aggiornato:

- `sql\looker_acl_operativa.md`

### 2026-04-11 - Estensione ACL con Master User (accesso totale)

Nuova esigenza:

- alcuni utenti devono vedere tutti i dati, non solo il proprio `ov_codice_cliente`

Soluzione implementata:

- convenzione ACL: `ov_codice_cliente = '__ALL__'` per accesso globale
- query Looker riscritta con `WHERE EXISTS`:
  - accesso per codice cliente specifico
  - oppure accesso totale se presente riga `__ALL__`

Aggiornamenti file:

- `sql\looker_acl_setup.sql`: aggiunto esempio `MERGE` per master user e query Looker aggiornata
- `sql\looker_acl_operativa.md`: aggiunte istruzioni operative per creare master user

### 2026-04-11 - Proposta software installabile con pagina configurazione

Richiesta:

- evolvere da script singolo a prodotto installabile, riutilizzabile su altri clienti
- permettere autonomia su:
  - viste SQL
  - frequenze aggiornamento
  - permessi ACL utente/email

Output prodotto:

- documento di proposta architetturale: `docs\proposta_software_configuratore.md`

Linee guida scelte:

- stack pragmatico: `FastAPI + UI web leggera + APScheduler + SQLite/PostgreSQL`
- moduli: Config Manager, View Manager, Pipeline Manager, Scheduler, ACL Manager, Monitoring
- roadmap a fasi per MVP rapido e successiva industrializzazione multi-cliente

### 2026-04-11 - Scaffold tecnico MVP software configuratore

Su richiesta "Procedi pure", e stato creato un primo MVP funzionante lato struttura progetto:

Cartella:

- `software_mvp\`

File principali creati:

- `software_mvp\README.md`
- `software_mvp\requirements.txt`
- `software_mvp\.env.example`
- `software_mvp\run_dev.ps1`
- `software_mvp\app\main.py`
- `software_mvp\app\models.py`
- `software_mvp\app\schemas.py`
- `software_mvp\app\services\sqlserver_service.py`
- `software_mvp\app\services\pipeline_service.py`
- `software_mvp\app\services\scheduler_service.py`
- `software_mvp\app\api\routes\{views,pipelines,schedules,acl,system}.py`
- `software_mvp\app\templates\index.html`

Funzioni incluse nel MVP:

- API CRUD per:
  - viste (`/api/views`)
  - pipeline (`/api/pipelines`)
  - schedule cron (`/api/schedules`)
  - ACL (`/api/acl`) con supporto master `__ALL__`
- publish di una view su SQL Server (`POST /api/views/{id}/publish`) via `CREATE OR ALTER VIEW`
- run manuale pipeline (`POST /api/pipelines/{id}/run`) con logging su `run_logs`
- scheduler automatico APScheduler che carica schedule attive dal DB configurazione
- homepage admin base con metriche rapide e link a `/docs`

Verifiche eseguite:

- compilazione sintattica moduli Python con `python -m compileall software_mvp\app`: esito OK

Prossimo step naturale (fase successiva):

- aggiungere autenticazione/ruoli utente applicazione
- aggiungere editor UI completo (non solo API docs)
- packaging installabile (servizio Windows / installer)

### 2026-04-11 - Comando corretto avvio MVP su PC produzione

Per evitare problemi di `python` non nel `PATH` o policy PowerShell, il comando consigliato sul PC produzione e:

- uso path Python completo: `C:\Users\datalab2\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- avvio da cartella app (es. `C:\BigQuery\software_mvp`)
- bootstrap venv + dipendenze + start uvicorn

### 2026-04-11 - Esito avvio MVP su produzione (errore bind porta)

Esito test reale ricevuto:

- installazione dipendenze completata correttamente
- startup app avvenuto
- errore in bind rete:
  - `WinError 10013` su `0.0.0.0:8080`

Correzione operativa indicata:

- avvio locale server con `--host 127.0.0.1 --port 8080`
- in alternativa cambiare porta (es. `8010`) se `8080` e bloccata
- usare `0.0.0.0` solo se necessario accesso da altri PC e con porta permessa da policy/firewall

### 2026-04-11 - Conferma accesso UI MVP

Confermato che la pagina web del configuratore MVP e visibile correttamente sul PC produzione.

Stato:

- backend FastAPI avviato
- homepage raggiungibile
- base pronta per procedere con step successivi (UI CRUD, autenticazione, packaging)

### 2026-04-11 - Implementazione UI CRUD completa nel MVP

Su richiesta "procedi con l'implementazione" e stata realizzata la UI operativa completa.

Backend:

- nuovo router web: `software_mvp\app\ui_routes.py`
- `main.py` aggiornato per includere router UI come entrypoint principale

Template aggiunti:

- `software_mvp\app\templates\base.html`
- `software_mvp\app\templates\dashboard.html`
- `software_mvp\app\templates\views_list.html`
- `software_mvp\app\templates\view_detail.html`
- `software_mvp\app\templates\pipelines_list.html`
- `software_mvp\app\templates\pipeline_detail.html`
- `software_mvp\app\templates\schedules.html`
- `software_mvp\app\templates\acl.html`
- `software_mvp\app\templates\not_found.html`

Template rimosso:

- `software_mvp\app\templates\index.html` (sostituito da dashboard + navigazione)

Funzionalita UI implementate:

- Dashboard con statistiche e ultimi run
- Views:
  - create/list/detail/update/delete
  - publish su SQL Server da pulsante UI
- Pipelines:
  - create/list/detail/update/delete
  - run manuale da UI con log visibile
- Schedules:
  - create/list/update/delete
  - validazione cron + reload scheduler
- ACL:
  - list/create/update/delete per tenant
  - supporto master user (`customer_code='__ALL__'`)

Documentazione aggiornata:

- `software_mvp\README.md` con nuovi link UI e flusso operativo da interfaccia

Verifica tecnica in questa sessione:

- `python -m compileall software_mvp\app`: OK
- test import runtime con Python di questa macchina non eseguito per dipendenza mancante (`fastapi` non installato in questo ambiente), mentre su PC produzione le dipendenze risultano installate

### 2026-04-11 - Fix avvio MVP in produzione (`ModuleNotFoundError: app`)

Errore ricevuto in produzione:

- `ModuleNotFoundError: No module named 'app'`

Causa:

- comando `uvicorn app.main:app` lanciato da directory diversa da `C:\BigQuery\software_mvp`

Comandi corretti:

- opzione 1 (consigliata): entrare nella cartella app e avviare da li
- opzione 2: usare `--app-dir C:\BigQuery\software_mvp` cosi il comando funziona da qualsiasi path

Documentazione aggiornata:

- `software_mvp\README.md` sezione troubleshooting

### 2026-04-11 - Fix dipendenza FastAPI Form (`python-multipart`)

Errore runtime ricevuto in avvio:

- `RuntimeError: Form data requires "python-multipart" to be installed`

Causa:

- i nuovi endpoint UI usano `Form(...)` e richiedono il package `python-multipart`

Correzione applicata:

- aggiunto `python-multipart==0.0.20` in `software_mvp\requirements.txt`
- aggiornata guida troubleshooting in `software_mvp\README.md`

Azione operativa in produzione:

- installare nel venv:
  - `C:\BigQuery\software_mvp\.venv\Scripts\python.exe -m pip install python-multipart==0.0.20`

### 2026-04-11 - Verifica dipendenze su produzione (requirements non allineato)

Output ricevuto dal comando `pip install -r requirements.txt` sul server:

- elenco pacchetti senza `python-multipart`
- conferma implicita che il file `C:\BigQuery\software_mvp\requirements.txt` in produzione e ancora la versione vecchia

Indicazione operativa:

- installare subito `python-multipart` manualmente
- poi riallineare i file di `software_mvp` dal workspace di sviluppo al server produzione

### 2026-04-11 - Esito installazione `python-multipart` e scelta porta runtime

Output ricevuto da produzione:

- `python-multipart==0.0.20` installato correttamente
- verifica import pacchetto: OK (`0.0.20`)
- avvio app: startup completato
- bind su `127.0.0.1:8080` bloccato da policy (`WinError 10013`)

Decisione operativa:

- usare porta `8010` come standard runtime su questo server

Aggiornamenti locali applicati:

- `software_mvp\run_dev.ps1` default port impostata a `8010`
- `software_mvp\README.md` URL e comandi aggiornati con porta `8010`

### 2026-04-11 - Conferma UI CRUD visibile su produzione

Confermato che sul server produzione sono visibili correttamente:

- dashboard
- pagine `Views`, `Pipelines`, `Schedules`, `ACL`

Stato attuale:

- MVP web operativo in esecuzione su `127.0.0.1:8010`
- base pronta per passare a hardening (autenticazione/ruoli) e packaging installabile

### 2026-04-11 - Implementazione autenticazione e ruoli applicazione

Su richiesta "Procedi", e stato implementato il layer auth/authorization nel MVP.

Modifiche backend:

- modello utenti applicazione `AppUser` aggiunto in `software_mvp\app\models.py`
- nuovo servizio password/auth:
  - `software_mvp\app\services\auth_service.py`
  - hashing password con PBKDF2-HMAC SHA256
  - funzioni login, normalizzazione ruoli, bootstrap admin
- `software_mvp\app\main.py` aggiornato con:
  - `SessionMiddleware`
  - middleware di protezione UI
  - enforcement ruoli:
    - `admin`: full
    - `operator`: write operativo
    - `viewer`: read-only UI
  - bootstrap admin al primo avvio da variabili `.env`
- `software_mvp\app\ui_routes.py` esteso con:
  - `/login` (GET/POST)
  - `/logout` (POST)
  - `/ui/users` (CRUD utenti + reset password, solo admin)

Modifiche UI:

- nuovi template:
  - `software_mvp\app\templates\login.html`
  - `software_mvp\app\templates\users.html`
- `software_mvp\app\templates\base.html` aggiornato con:
  - utente corrente e ruolo in topbar
  - pulsante logout
  - menu `Users` visibile solo ad admin

Configurazione:

- `software_mvp\.env.example` esteso con:
  - `APP_SESSION_SECRET`
  - `APP_ADMIN_USERNAME`
  - `APP_ADMIN_PASSWORD`
- `software_mvp\README.md` aggiornato con:
  - URL login
  - pagina users
  - sezione ruoli e accessi

Verifica:

- compilazione moduli `software_mvp\app` con `python -m compileall`: OK

Aggiornamento successivo nello stesso step auth:

- middleware esteso anche alle API:
  - API protette da sessione (eccetto `/api/system/health`)
  - write API consentita solo a `admin/operator`
  - write API ACL consentita solo a `admin`
- `README` esteso con note bootstrap admin da `.env` e raccomandazione cambio password iniziale

### 2026-04-11 - Fix dipendenza sessioni (`itsdangerous`)

Errore ricevuto in produzione:

- `ModuleNotFoundError: No module named 'itsdangerous'`

Causa:

- `SessionMiddleware` di Starlette richiede `itsdangerous`

Correzione applicata:

- aggiunto `itsdangerous==2.2.0` in `software_mvp\requirements.txt`
- aggiornata sezione troubleshooting in `software_mvp\README.md`

### 2026-04-11 - Internal Server Error dopo login (produzione)

Nuovo sintomo riportato:

- pagina `/login` visibile
- dopo submit login: `Internal Server Error`

Ipotesi tecnica principale:

- deployment parziale/non allineato dei file `software_mvp` tra ambiente sviluppo e produzione
- possibile mismatch tra codice Python e cartella `templates` (es. template mancanti o vecchi)

Azione operativa consigliata:

- sincronizzare l'intera cartella `C:\BigQuery\software_mvp` con la versione corrente completa
- rilanciare install dipendenze da `requirements.txt`
- riavviare uvicorn su porta `8010`
- in caso persistenza, acquisire traceback completo da console uvicorn per fix puntuale

### 2026-04-11 - Errore avvio dopo ripristino cartella (venv mancante)

Nuovo errore riportato:

- `C:\BigQuery\software_mvp\.venv\Scripts\python.exe` non riconosciuto / file non trovato

Interpretazione:

- dopo ripristino della cartella, l'ambiente virtuale `.venv` non e presente (o non e stato copiato)

Correzione operativa:

- ricreare `.venv` con Python di sistema
- reinstallare dipendenze da `requirements.txt`
- riavviare uvicorn su `127.0.0.1:8010`

### 2026-04-11 - App avviata ma pagina non caricata

Nuovo sintomo riportato:

- processo web avviato
- pagina non si carica lato browser

Diagnosi primaria:

- con bind `--host 127.0.0.1` il servizio e raggiungibile solo dal server locale
- da altri PC in rete la pagina non risponde finche non si usa host `0.0.0.0` + porta consentita firewall/policy

Check operativo suggerito:

- test locale da server su `/api/system/health` e `/login`
- verifica socket in ascolto su porta `8010`
- se accesso remoto necessario, aprire regola firewall e avviare su `0.0.0.0:8010`

### 2026-04-11 - Esito check locale con porta 8010

Risultati ricevuti dal server:

- `Invoke-WebRequest` su `127.0.0.1:8010` fallisce con "Impossibile effettuare la connessione"
- `Get-NetTCPConnection -LocalPort 8010 -State Listen` non trova listener

Conclusione:

- servizio web non in esecuzione (oppure avvio fallisce e processo termina subito)

Passo successivo richiesto:

- avvio uvicorn con logging dettagliato su file per catturare l'errore reale di startup

### 2026-04-11 - Chiarimento comando uvicorn "bloccato"

Nota operativa:

- il comando `uvicorn` lanciato direttamente in PowerShell resta in foreground e mantiene la console occupata
- comportamento atteso: sembra "bloccato" ma in realta il server puo essere in esecuzione

Modalita consigliata:

- avvio in processo separato (`Start-Process`) con log su file
- verifica listener porta 8010 e test endpoint `/api/system/health`

### 2026-04-11 - Errore Start-Process su redirect log

Errore rilevato:

- `Start-Process` non accetta `-RedirectStandardOutput` e `-RedirectStandardError` sullo stesso file

Correzione:

- usare due file distinti (`stdout` e `stderr`)
- oppure usare `cmd /c` con redirect `2>&1` verso un file unico

### 2026-04-11 - Verifica runtime positiva su porta 8010

Check eseguiti sul server produzione:

- `Get-NetTCPConnection -LocalPort 8010 -State Listen`: listener attivo su `127.0.0.1:8010`
- `Invoke-WebRequest http://127.0.0.1:8010/api/system/health`: risposta `200 OK` con body `{"status":"ok"}`

Conclusione:

- backend MVP avviato e raggiungibile correttamente in locale su porta `8010`

### 2026-04-11 - Nuovo sintomo "impossibile raggiungere il sito"

Diagnosi coerente con i test precedenti:

- listener attivo su `127.0.0.1:8010` (solo loopback)
- da PC diversi dal server il sito non e raggiungibile finche il bind resta su `127.0.0.1`

Indicazione operativa:

- se accesso richiesto solo dal server: usare URL locale `http://127.0.0.1:8010/login`
- se accesso richiesto da rete:
  - avviare uvicorn su `0.0.0.0:8010`
  - aprire regola firewall inbound TCP 8010
  - usare URL `http://<IP_SERVER>:8010/login`

### 2026-04-11 - Chiarimento: accesso dal PC server stesso

Se il test health da PowerShell e `200 OK` ma il browser sullo stesso server non apre la pagina, verificare:

- URL esatto in browser: `http://127.0.0.1:8010/login` (non `https`)
- processo uvicorn ancora attivo (se avviato in foreground, chiudendo la shell il server si ferma)
- assenza di redirect/proxy locale che forzano HTTPS

Test locale rapido consigliato:

- `Invoke-WebRequest http://127.0.0.1:8010/login -UseBasicParsing`
- `Start-Process "http://127.0.0.1:8010/login"`

### 2026-04-11 - Diagnosi finale su "sito non raggiungibile" (server locale)

Output ricevuto dal server:

- `Invoke-WebRequest http://127.0.0.1:8010/login` -> connessione fallita
- `Get-NetTCPConnection -LocalPort 8010 -State Listen` -> nessun listener

Conclusione certa:

- applicazione non in esecuzione al momento del test (problema non browser/firetwall)

Azione operativa:

- avviare uvicorn in processo separato con log
- verificare listener attivo prima di aprire il browser

### 2026-04-11 - Conferma definitiva listener e health su 8010

Verifica ricevuta dal server:

- `Get-NetTCPConnection -LocalPort 8010 -State Listen` -> listener attivo su `127.0.0.1:8010`
- `Invoke-WebRequest http://127.0.0.1:8010/api/system/health` -> `200 OK` con `{"status":"ok"}`

Stato:

- runtime MVP correttamente avviato e raggiungibile in locale

### 2026-04-11 - Nuovo errore 500 su login

Sintomo riportato:

- dopo disponibilita servizio (`health` OK), il submit login restituisce `Internal Server Error`

Stato analisi:

- problema applicativo a runtime (non rete/porta)
- necessario acquisire traceback server (`uvicorn_err.log`) per fix puntuale

### 2026-04-11 - Root cause 500 login identificata e fix applicato

Traceback acquisito:

- `AssertionError: SessionMiddleware must be installed to access request.session`

Causa tecnica:

- middleware auth function-based eseguito prima del `SessionMiddleware` per ordine di registrazione

Fix codice applicato:

- in `software_mvp\app\main.py` il `app.add_middleware(SessionMiddleware, ...)` e stato spostato dopo la definizione di `@app.middleware("http")`
- aggiunto commento tecnico nel codice per evitare regressioni future sull'ordine middleware

### 2026-04-11 - Persistenza 500 dopo fix: check processo/codice attivo

Nuovo sintomo:

- `Internal Server Error` ancora presente dopo deploy fix middleware

Verifiche da eseguire:

- fermare eventuale processo uvicorn precedente in ascolto su porta `8010`
- confermare che `C:\BigQuery\software_mvp\app\main.py` sul server contiene il fix ordine middleware
- riavviare uvicorn in foreground con `--log-level debug` e raccogliere nuovo traceback

### 2026-04-11 - Stato finale sessione sviluppo (stop richiesto)

Esito ultimo riscontro dal server produzione:

- applicazione avviata correttamente
- login funzionante
- pagina `Users` non funzionante (issue aperta da correggere nel prossimo step)

Decisione operativa:

- sviluppo fermato a questo punto su richiesta
- ripartenza prevista dalla correzione pagina `Users` e successivo hardening/packaging

### 2026-04-13 - Ripartenza lavori e fix robustezza pagina Users

Obiettivo ripartenza:

- riprendere dal punto aperto: malfunzionamento pagina `Users`

Analisi tecnica:

- il codice era vulnerabile a sessioni legacy/corrotte con `user_id` non numerico
- in quel caso alcune route (in particolare `Users`) potevano generare errore 500 durante il cast dell'ID sessione

Fix applicati:

- `software_mvp\app\ui_routes.py`
  - aggiunta funzione `_session_user_id(request)` con parsing sicuro dell'ID sessione
  - se `user_id` non e valido: pulizia sessione (`request.session.clear()`) e ritorno `None`
  - aggiornato `_get_current_user(...)` per usare il parsing sicuro
  - allineati i confronti ID in update/delete utenti al nuovo helper
- `software_mvp\app\main.py`
  - nel middleware auth aggiunta validazione/cast sicuro di `user_id`
  - in caso di valore non valido: sessione azzerata e redirect/login forzato

Verifica locale codice:

- eseguito `python -m py_compile software_mvp\app\main.py software_mvp\app\ui_routes.py` con esito OK

Nota operativa per produzione:

- dopo deploy di questi file, conviene fare logout/login (o cancellare cookie browser) per eliminare eventuali sessioni vecchie

### 2026-04-13 - Hardening aggiuntivo errore 500 pagina Users

Nuovo riscontro:

- pagina `Users` ancora in `Internal Server Error` su ambiente produzione

Intervento applicato:

- `software_mvp\app\database.py`
  - aggiunta migrazione automatica legacy per SQLite all'avvio (`_run_sqlite_legacy_migrations`)
  - se tabella `app_users` esiste ma e vecchia, vengono aggiunte automaticamente le colonne mancanti:
    - `role`
    - `is_active`
    - `created_at`
    - `updated_at`
  - normalizzazione dati legacy:
    - `role` vuoto/null -> `viewer`
    - `is_active` null -> `1`
- `software_mvp\app\ui_routes.py`
  - route `GET /ui/users` resa resiliente: errori DB gestiti senza 500 (messaggio in pagina)
  - route utenti (`create/update/password/delete`) con `try/except` + rollback su errori DB

Verifica codice:

- `python -m py_compile software_mvp\app\database.py software_mvp\app\ui_routes.py software_mvp\app\main.py` -> OK

Nota deploy:

- dopo sincronizzazione file su `C:\BigQuery\software_mvp`, riavviare uvicorn per applicare la migrazione auto al bootstrap

### 2026-04-13 - Nuovo fix su SessionMiddleware (errore assert in auth_middleware)

Traceback ricevuto da produzione:

- `AssertionError: SessionMiddleware must be installed to access request.session`
- stack su `app\main.py` in `auth_middleware` durante `request.session.get("role")`

Diagnosi:

- in runtime il middleware auth puo essere eseguito quando la sessione non e ancora nel `scope`
- accesso diretto a `request.session` in quel punto provoca assert e HTTP 500

Fix applicato:

- `software_mvp\app\main.py`
  - nel middleware auth sostituito accesso diretto `request.session` con lettura difensiva da `request.scope.get("session")`
  - in assenza sessione: richiesta trattata come non autenticata (nessun crash)
- `software_mvp\app\ui_routes.py`
  - helper `_session_user_id` reso difensivo su `request.scope["session"]`
  - `login_submit` controlla disponibilita sessione e mostra errore gestito invece di 500
  - `logout` usa clear difensivo

Verifica locale:

- `python -m py_compile software_mvp\app\main.py software_mvp\app\ui_routes.py software_mvp\app\database.py` -> OK

### 2026-04-13 - Troubleshooting log path su server produzione

Nuovo riscontro operativo:

- comando `Get-Content "$app\uvicorn_err.log"` ha cercato `C:\uvicorn_err.log`

Causa:

- variabile `$app` non valorizzata nella shell corrente (o sessione PowerShell nuova)

Correzione:

- reimpostare `$app = "C:\BigQuery\software_mvp"` prima dei comandi log
- in alternativa usare percorso assoluto diretto:
  - `Get-Content "C:\BigQuery\software_mvp\uvicorn_err.log" -Tail 120`

### 2026-04-13 - Diagnosi test finale: server non in ascolto al momento della prova

Output ricevuto:

- nei log erano presenti richieste precedenti con `200/303`
- durante il test live `Invoke-WebRequest` su `/login` e `/ui/users` ha dato:
  - `Impossibile effettuare la connessione al server remoto`

Conclusione:

- nel momento del test il processo uvicorn non era in ascolto su `127.0.0.1:8010` (log presenti ma non live)

Azione operativa:

- riavvio uvicorn in background con `WorkingDirectory` esplicita, log separati e controllo listener prima dei test HTTP

### 2026-04-13 - Fix aggiuntivo specifico pagina Users (sessione+DB)

Nuovo sintomo riportato:

- login OK
- errore interno solo su pagina `Users`

Fix applicato in codice:

- `software_mvp\app\ui_routes.py`
  - `_get_current_user(...)` ora gestisce errori DB con `try/except` + `rollback`
  - in caso errore DB o utente non valido, sessione pulita in modo difensivo e ritorno `None`

Motivazione:

- se schema `app_users` non perfettamente allineato o DB in stato transitorio, la pagina `Users` non deve andare in 500
- il sistema deve degradare in modo controllato (utente non autenticato / messaggio gestito)

### 2026-04-13 - Errore copia file su server produzione (path sorgente assente)

Output produzione:

- `Copy-Item` da `C:\Progetti clienti\Vtronik\BI\software_mvp\app\...` fallito con `PathNotFound`
- `health` su `http://127.0.0.1:8010/api/system/health` risponde `200 OK`

Conclusione:

- sul server produzione non esiste la cartella sorgente sviluppo locale usata nel comando copia
- servizio uvicorn attivo correttamente, ma i fix non sono stati sincronizzati tramite quel comando

Azione successiva definita:

- usare una procedura "solo produzione": validazione contenuto file direttamente in `C:\BigQuery\software_mvp\app`
- applicare eventuali fix direttamente sui file presenti sul server e riavviare uvicorn

### 2026-04-13 - Nota operativa infrastrutturale (reti separate)

Conferma utente:

- PC sviluppo (`C:\Progetti clienti\Vtronik\BI`) e PC produzione (`C:\BigQuery\software_mvp`) sono su reti completamente diverse
- sincronizzazione file avviene manualmente da parte utente

Implicazione:

- non usare piu comandi di copia diretta tra i due path da eseguire sul server produzione
- fornire verifiche/fix con approccio "file gia copiati" + riavvio/test locale su produzione

### 2026-04-13 - Variabile PowerShell non persistente tra shell (log path)

Nuovo riscontro:

- dopo riavvio riuscito (`health` 200), lettura log fallita con path `C:\uvicorn_err.log` e `C:\uvicorn_out.log`

Causa tecnica:

- la variabile `$app` non era valorizzata nella shell da cui sono stati letti i log
- con `$app` vuota, il path risolto diventa `C:\...`

Correzione operativa:

- usare path assoluti diretti per i log (`C:\BigQuery\software_mvp\uvicorn_err.log`, `...uvicorn_out.log`)
- oppure ridefinire sempre `$app` all'inizio di ogni nuova shell PowerShell

### 2026-04-13 - Root cause definitivo pagina Users (NameError ROLE_OPERATOR)

Traceback produzione acquisito:

- `NameError: name 'ROLE_OPERATOR' is not defined`
- punto errore: `app\ui_routes.py` nella route `ui_users` durante costruzione lista ruoli

Causa:

- mancava import `ROLE_OPERATOR` da `services.auth_service`

Fix applicato:

- in `software_mvp\app\ui_routes.py` aggiunto `ROLE_OPERATOR` all'import:
  - `from .services.auth_service import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, ...`

Verifica:

- `python -m py_compile software_mvp\app\ui_routes.py` -> OK

Esito atteso post-deploy:

- `/ui/users` non deve piu restituire 500

### 2026-04-13 - Conferma risoluzione produzione pagina Users

Conferma utente:

- dopo deploy del fix import `ROLE_OPERATOR`, la pagina `Users` funziona correttamente

Stato:

- issue `Internal Server Error` su `/ui/users` chiusa

### 2026-04-13 - Piano collaudo funzionale guidato (MVP configuratore)

Obiettivo:

- verificare funzione per funzione la reale usabilita applicativa
- validare configurazione minima per ogni pagina
- validare ruoli (`admin`, `operator`, `viewer`)

Prerequisiti test:

- app attiva su `http://127.0.0.1:8010`
- login admin funzionante
- file `.env` valorizzato (almeno `APP_SESSION_SECRET`)
- per test publish view: `SQLSERVER_CONN_STR` valido

Dataset test consigliato (tenant unico):

- tenant: `vtronik_test`
- view:
  - schema: `dbo`
  - nome: `vw_test_ordini`
  - sql: `SELECT TOP 10 DocEntry, DocNum FROM ORDR`
- pipeline:
  - nome: `pipe_test_ordini`
  - source_view_id: ID della view appena creata
  - dataset: `sap_reporting`
  - table: `stato_ordini_cliente_test`
  - command (test OK): `cmd /c "echo PIPELINE_OK"`
- schedule:
  - cron: `*/5 * * * *`
  - timezone: `Europe/Rome`
- ACL:
  - `utente.test@azienda.it` -> `C0001`
  - `master.test@azienda.it` -> `__ALL__`

Sequenza collaudo consigliata:

1) Login/Sessione
- test login corretto e login errato
- test logout
- expected: redirect corretti e nessun 500

2) Dashboard
- verifica caricamento contatori e tabella run
- expected: pagina stabile e aggiornata

3) Views (`/ui/views`)
- crea view test
- apri dettaglio view e modifica SQL (version deve incrementare)
- publish view su SQL Server
- expected:
  - create/update senza errori
  - publish OK se connessione SQL valida

4) Pipelines (`/ui/pipelines`)
- crea pipeline test collegata alla view
- run manuale da dettaglio pipeline
- expected:
  - creazione OK
  - run log con stato `OK` e messaggio stdout

5) Schedules (`/ui/schedules`)
- crea schedule attiva con cron valido
- prova cron non valido (deve fallire con messaggio)
- disattiva/riattiva schedule
- expected:
  - validazione cron attiva
  - reload scheduler senza crash

6) ACL (`/ui/acl`)
- crea regola standard e regola master `__ALL__`
- modifica nota/stato attivo
- expected:
  - univocita regole rispettata
  - nessun 500 in create/update/delete

7) Users (`/ui/users`)
- crea utente `operator` e `viewer`
- reset password utente
- verifica vincoli:
  - non eliminare utente loggato
  - non rimuovere/disattivare ultimo admin
- expected:
  - vincoli rispettati
  - pagina stabile (issue 500 risolta)

8) Matrice permessi ruoli
- login admin: tutto consentito
- login operator: no modifica ACL, no users
- login viewer: sola lettura pagine UI
- expected: redirect/deny coerenti senza errori runtime

Esito collaudo:

- al termine compilare check pass/fail per ogni punto
- eventuali fail con screenshot + traceback `uvicorn_err.log`

### 2026-04-13 - Esito collaudo parziale (Login + Views)

Riscontro utente:

- Login: tutti i test OK
- Views:
  - creazione OK
  - apertura dettaglio OK
  - modifica OK
  - publish KO con errore ODBC

Errore publish riportato:

- `('08001', '[08001] [Microsoft][ODBC Driver 17 for SQL Server]The client cannot connect to the server because the requested instance was not available ...')`

Interpretazione:

- errore infrastrutturale di connessione SQL Server (istanza/host/porta), non errore applicativo della UI

Azione:

- procedere con verifica `SQLSERVER_CONN_STR` e raggiungibilita istanza SQL Server dal PC produzione

### 2026-04-13 - Nuova funzione: configurazione SQL Server direttamente in app

Richiesta:

- gestire la configurazione collegamento DB (SQL Server) tramite apposita funzione in UI

Implementazione completata:

- aggiunta pagina admin `Settings`:
  - route GET: `/ui/settings`
  - route POST save: `/ui/settings/sqlserver/save`
  - route POST test: `/ui/settings/sqlserver/test`
- nuova tabella configurazioni applicative:
  - `app_settings` (`key`, `value`, `updated_at`)
  - chiave usata: `sqlserver_conn_str`
- `Publish View` aggiornato:
  - usa prima il valore salvato in `Settings`
  - se vuoto, fallback su `.env` (`SQLSERVER_CONN_STR`)
- aggiunto test connessione SQL Server da UI:
  - verifica reale con `pyodbc.connect(..., timeout=8)`
  - query test: `SELECT @@SERVERNAME, DB_NAME()`

Permessi:

- pagina `Settings` accessibile solo ad `admin` (allineata al middleware auth)

File toccati:

- `software_mvp\app\models.py` (nuovo model `AppSetting`)
- `software_mvp\app\services\sqlserver_service.py` (config runtime + test connessione)
- `software_mvp\app\ui_routes.py` (nuove route UI settings)
- `software_mvp\app\main.py` (admin-only per `/ui/settings`)
- `software_mvp\app\templates\settings.html` (nuova pagina)
- `software_mvp\app\templates\base.html` (voce menu `Settings`)
- `software_mvp\README.md` (documentazione pagina settings)

Verifica codice:

- `python -m py_compile software_mvp\app\main.py software_mvp\app\models.py software_mvp\app\ui_routes.py software_mvp\app\services\sqlserver_service.py` -> OK

### 2026-04-13 - Estensione Settings: configurazione BigQuery + pipeline managed

Richiesta:

- aggiungere in app la configurazione BigQuery per gestire il piu possibile il funzionamento end-to-end

Implementazione:

1) Configurazione BigQuery in `Settings` (solo admin)
- nuovi campi gestiti:
  - `bq_project_id`
  - `bq_default_dataset`
  - `bq_default_table`
  - `bq_location`
  - `bq_credentials_file`
- nuove azioni UI:
  - `Salva BigQuery`
  - `Test connessione BigQuery`
  - `Crea/valida dataset BigQuery` (bootstrap)

2) Persistenza impostazioni applicative
- riuso tabella `app_settings` (key/value)
- fallback automatico su `.env` se i valori in app sono vuoti

3) Modalita pipeline managed (senza script esterni)
- aggiornato `pipeline_service`:
  - se `command` valorizzato: comportamento invariato (esecuzione comando custom)
  - se `command` vuoto: modalita managed
    - legge dati da SQL Server usando `select_sql` della view sorgente (`source_view_id`)
    - carica su BigQuery con `load_table_from_json` e `autodetect=True`
    - supporta `write_mode` (`WRITE_TRUNCATE`, `WRITE_APPEND`, `WRITE_EMPTY`)
    - salva nel `RunLog` anche `rows_extracted` e `rows_loaded`

4) Servizi nuovi/estesi
- nuovo file `software_mvp\app\services\bigquery_service.py`
  - test connessione BigQuery
  - bootstrap dataset
  - estrazione righe da SQL Server + load su BigQuery
- esteso `software_mvp\app\services\sqlserver_service.py`
  - connessione SQL Server effettiva da settings + fallback `.env`

5) UI/documentazione
- aggiornata `settings.html` con sezioni SQL Server e BigQuery
- aggiornate pagine pipeline (`pipelines_list`, `pipeline_detail`) con nota managed mode
- aggiornati `.env.example` e `README.md` con parametri BigQuery e flusso operativo
- aggiornata `requirements.txt`:
  - `google-cloud-bigquery==3.41.0`
  - `google-auth==2.49.1`

Verifica tecnica locale:

- `python -m py_compile software_mvp\app\config.py software_mvp\app\models.py software_mvp\app\services\sqlserver_service.py software_mvp\app\services\bigquery_service.py software_mvp\app\services\pipeline_service.py software_mvp\app\ui_routes.py` -> OK

### 2026-04-13 - Wizard connection string SQL Server / SAP HANA

Nuova richiesta:

- evitare compilazione manuale della connection string
- introdurre un wizard guidato
- tenere conto di possibile utilizzo futuro SAP HANA oltre a SQL Server

Implementazione:

1) Wizard in `UI Settings`
- nuova sezione: `Wizard Connection String (SQL Server / HANA)`
- supporto due engine:
  - `sqlserver`
  - `hana`
- pulsante unico: `Genera e Applica dal wizard`

2) Costruzione guidata SQL Server
- campi wizard:
  - driver
  - server
  - istanza (opzionale)
  - porta (opzionale)
  - database
  - uid
  - password
  - encrypt
  - trust server certificate
- output generato in formato ODBC SQL Server
- salvataggio automatico su setting applicativo `sqlserver_conn_str`

3) Costruzione guidata SAP HANA
- campi wizard:
  - driver (`HDBODBC`)
  - server
  - porta
  - database (opzionale)
  - uid
  - password
  - encrypt
- output generato in formato ODBC HANA (`SERVERNODE=host:port`)
- salvataggio su setting applicativo dedicato `hana_conn_str`

4) Stato engine sorgente
- nuovo setting: `source_db_engine` (`sqlserver` / `hana`)
- visualizzato in pagina Settings

5) Compatibilita attuale
- `Publish View` e modalita managed pipeline restano orientati a SQL Server
- configurazione HANA e disponibile per preparare evoluzione multi-db

File aggiornati:

- `software_mvp\app\ui_routes.py` (builder + endpoint wizard + settings context esteso)
- `software_mvp\app\templates\settings.html` (nuova UI wizard + visualizzazione stringa HANA)
- `software_mvp\README.md` (documentazione formati SQL/HANA)

Verifica:

- `python -m py_compile software_mvp\app\ui_routes.py software_mvp\app\services\pipeline_service.py software_mvp\app\services\bigquery_service.py software_mvp\app\services\sqlserver_service.py software_mvp\app\config.py software_mvp\app\models.py` -> OK

### 2026-04-25 - Installer Windows trasportabile (.exe)

Obiettivo:

- passare da distribuzione zip+script a installer `.exe` riusabile su installazioni cliente.

Implementazione:

1) Script Inno Setup
- file: `software_mvp\installer\Esyy_B1Connector.iss`
- comportamento:
  - installazione in `C:\Program Files\Esyy\B1Connector`
  - copia dei file applicativi essenziali (senza `.venv` / `.env` locali)
  - setup runtime con creazione `.venv` e install dipendenze
  - installazione autostart selezionabile (SYSTEM o utente corrente)
  - collegamenti Start Menu / desktop
  - rimozione task su uninstall

2) Builder installer
- file: `software_mvp\build_installer.ps1`
- funzioni:
  - crea payload pulito in `dist\installer_payload\...`
  - rileva `ISCC.exe` (Inno Setup)
  - compila setup in `dist\installer\`
  - supporta versione parametrica

3) Setup script esteso
- file: `software_mvp\setup_windows.ps1`
- aggiunti parametri:
  - `TaskName`
  - `UseCurrentUser`
- pass-through verso `install_autostart_task.ps1`

4) Task naming allineato prodotto
- file: `software_mvp\install_autostart_task.ps1`
- file: `software_mvp\uninstall_autostart_task.ps1`
- task di default aggiornato a `EsyyB1Connector`

5) Setup one-click allineato
- file: `software_mvp\install_client.cmd`
- ora usa `-TaskName "EsyyB1Connector"`

6) Packaging zip aggiornato
- file: `software_mvp\package_release.ps1`
- inclusi:
  - `build_installer.ps1`
  - cartella `installer\`

7) Documentazione aggiornata
- file: `software_mvp\README.md`
  - aggiunta sezione build installer `.exe`
- file: `docs\installer_windows.md`
  - guida operativa build/install/verifica/troubleshooting installer

### 2026-04-25 - Trasferimento su repository GitHub

Obiettivo:

- versionare il progetto Esyy B1Connector su repository remoto dedicato.

Attivita eseguite:

1) Verifica repository locale
- path progetto usato: `C:\Esyy Suite\esyy-B1Connector`
- branch locale: `main`
- commit iniziale presente: `6c9438b` (`Initial import: Esyy B1Connector app, docs, scripts, installer`)

2) Push su GitHub
- remote: `https://github.com/eimnos/esyy-B1Conector.git`
- push eseguito con: `git push -u origin HEAD:main`
- tracking impostato: `main -> origin/main`

3) Verifica remota
- head remoto confermato: `refs/heads/main -> 6c9438b81a50d07741e185960b7e8c13b1f3452d`

### 2026-04-25 - UX/UI Wizard Redesign (Sprint 1 avviato)

Obiettivo:

- recepire la specifica UX/UI `docs/ux_ui_wizard_redesign.md` e applicare il primo sprint senza toccare logica pipeline/ACL/scheduler.

Implementazione:

1) Nuova app shell grafica
- aggiornato `software_mvp/app/templates/base.html`
- introdotti:
  - sidebar scura con logo + menu business
  - header chiaro con azioni (`Guide`, `API Docs`, utente, `Logout`)
  - mapping nav da voci tecniche a macro-sezioni (`Panoramica`, `Configurazioni`, `Riepiloghi`, `Monitoraggio`, `Utenti e accessi`, `Avanzate`)

2) CSS dedicato al nuovo layout
- creato `software_mvp/app/static/css/esyy-ui.css`
- aggiunti token e classi per:
  - shell 2 colonne
  - sidebar/menu con icone inline SVG
  - header e badge utente
  - responsive tablet/mobile
- `base.html` ora carica anche `/static/css/esyy-ui.css`

3) Route business di compatibilita
- aggiornato `software_mvp/app/ui_routes.py`
- aggiunte route:
  - `GET /ui/overview`
  - `GET /ui/configurations` (redirect a `/ui/views`)
  - `GET /ui/summaries`
  - `GET /ui/monitoring`
  - `GET /ui/users-access` (redirect admin -> `/ui/users`, altri -> `/ui/acl`)
  - `GET /ui/advanced`
- `/` ora usa `active_nav=overview`

4) Pagina Avanzate iniziale
- creato template `software_mvp/app/templates/advanced.html`
- include warning per utenti tecnici e link a pagine raw (views/pipelines/schedules/acl/settings/users)

Note tecniche:

- in questo ambiente locale non e stato possibile eseguire test runtime completi (python/venv non utilizzabile), quindi la verifica finale UI va eseguita sul PC operativo con i comandi standard di avvio.
