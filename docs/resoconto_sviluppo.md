# Resoconto Sviluppo Esyy B1Connector

## 2026-05-01 - Persistenza wizard su database

- Aggiunto modello `WizardSession` in `software_mvp/app/models.py` per salvare stato e bozza wizard.
- Estesa migrazione legacy SQLite in `software_mvp/app/database.py` con supporto tabella `wizard_sessions` e indici.
- Creato servizio `software_mvp/app/services/wizard_session_service.py` con funzioni:
  - `get_or_create_session`
  - `get_session`
  - `save_step_data`
  - `move_to_step`
  - `move_next`
  - `move_back`
  - `mark_completed`
  - `set_test_result`
  - `calculate_progress`
- Aggiornata route `GET /ui/wizard/{wizard_id}`:
  - sessione wizard caricata da DB
  - ripresa step da `current_step_id`
  - caricamento dati da `draft_data_json`
  - fallback temporaneo da bozza browser solo per migrazione.
- Aggiornata route `POST /ui/wizard/{wizard_id}`:
  - azioni `save`, `continue`, `back` persistite su DB
  - ultimo step con validazione campi obbligatori prima di `completed`.
- Aggiornata pagina `GET /ui/configurations`:
  - stato card letto da `WizardSession`
  - progress calcolato da dati salvati
  - ultimo aggiornamento da `updated_at`.
- Aggiornata pagina `GET /ui/summaries`:
  - nuovo template `software_mvp/app/templates/summaries.html`
  - stato reale wizard + azione "Modifica con wizard".
- Verifiche locali:
  - `py_compile` OK su file modificati.
  - Test runtime HTTP non eseguibile in questa macchina per virtualenv locale non riutilizzabile (path Python non presente).

## 2026-05-01 - Validazione runtime end-to-end wizard persistenti

- Virtualenv locale ricreato in `software_mvp/.venv` (Python 3.11) e dipendenze reinstallate.
- Test `py_compile` eseguito con successo su:
  - `app/main.py`
  - `app/ui_routes.py`
  - `app/models.py`
  - `app/database.py`
  - `app/services/wizard_definitions.py`
  - `app/services/wizard_session_service.py`
- Avvio FastAPI su `127.0.0.1:8010` OK.
- Migrazione `wizard_sessions` verificata runtime su `configurator.db`:
  - tabella presente
  - colonne attese presenti.
- Verifica HTTP UI completata su:
  - `/ui/configurations`
  - `/ui/wizard/full`
  - `/ui/wizard/sap`
  - `/ui/wizard/bigquery`
  - `/ui/summaries`
- Test persistenza wizard SAP completato:
  - `Salva bozza` mantiene step corrente
  - refresh mantiene step e dati
  - logout/login mantiene stato
  - riavvio app mantiene stato.
- Test completamento wizard SAP completato:
  - `wizard_sessions.status = completed`
  - card in `/ui/configurations` mostra `Completato` e `100%`
  - `/ui/summaries` mostra stato reale `Completato`
  - azione “Modifica con wizard” presente verso `/ui/wizard/sap`.

## 2026-05-01 - Wizard SAP operativo (apply su settings reali)

- Implementato apply reale del wizard SAP al **solo ultimo step** (conferma finale).
- Aggiunta logica in `ui_routes.py`:
  - `_apply_sap_wizard_to_settings(...)` legge bozza wizard da `wizard_sessions`.
  - valida campi SAP necessari (`engine`, `server`, `database`, `uid`, `pwd`, `test=result=ok`).
  - se `engine=sqlserver`:
    - costruisce connection string finale
    - esegue test connessione SQL Server
    - salva setting reali:
      - `source_db_engine=sqlserver`
      - `sqlserver_conn_str=<valore finale>`
  - se `engine=hana`:
    - costruisce connection string HANA
    - salva setting reali:
      - `source_db_engine=hana`
      - `hana_conn_str=<valore finale>`
- In caso di errore apply (validazione o test SQL):
  - il wizard **non** viene completato
  - stato sessione impostato a `test_failed`
  - errore mostrato in pagina wizard.
- In caso di successo apply:
  - wizard marcato `completed`
  - messaggio finale con dettaglio applicazione settings.
- Confermato che gli step intermedi continuano a salvare solo bozza (`wizard_sessions`) senza toccare `app_settings`.

## 2026-05-01 - Guida e script collaudo SAP wizard

- Aggiunto manuale operativo:
  - `docs/collaudo_wizard_sap_b1.md`
- Aggiunto script PowerShell di collaudo:
  - `scripts/collaudo_wizard_sap_b1.ps1`
- Lo script:
  - si posiziona automaticamente in `software_mvp`
  - esegue `py_compile`
  - avvia FastAPI su `127.0.0.1:8010`
  - stampa gli URL utili del collaudo
  - legge stato SQLite in modo sicuro:
    - `source_db_engine`
    - presenza/assenza `sqlserver_conn_str` e `hana_conn_str`
    - stato wizard SAP in `wizard_sessions`
- Sicurezza output:
  - nessuna password stampata
  - connection string completa mai stampata
  - server/database mostrati in forma mascherata.

## 2026-05-01 - Harden script collaudo su ambienti non migrati

- Aggiornato `scripts/collaudo_wizard_sap_b1.ps1` per gestire il caso in cui la tabella `wizard_sessions` non esista ancora.
- Nuovo comportamento:
  - non genera piu` traceback Python
  - stampa stato `wizard_sessions_table: assente`
  - mostra hint operativo: eseguire `init_db()` una volta per creare la tabella.

## 2026-05-01 - Allineamento produzione wizard_sessions

- Diagnostica eseguita su ambiente produzione:
  - `ImportError` iniziale confermava `app\models.py` non allineato (assenza `WizardSession`).
  - Copia file aggiornata in produzione e verifica `Select-String` positiva su `models.py` e `database.py`.
- Eseguita inizializzazione DB esplicita:
  - `init_db()` + `Base.metadata.create_all(bind=engine)`.
- Verifica finale su `configurator.db`:
  - tabella `wizard_sessions` presente.
  - elenco tabelle include `wizard_sessions`.
- Esito: persistenza wizard pronta anche in produzione.

## 2026-05-01 - Verifica runtime wizard reale su porte 8012 e 8010

- Test HTTP autenticato eseguito su `http://127.0.0.1:8012/ui/wizard/sap`:
  - pagina wizard step-by-step reale confermata (`Passo 1 di 6`, pulsanti `Salva bozza` e `Conferma e continua`).
- Test HTTP autenticato eseguito su `http://127.0.0.1:8010/ui/wizard/sap`:
  - stessa pagina wizard reale confermata.
- Nota:
  - il blocco HTML usa ancora classi CSS con naming `wizard-stub-*` in alcuni contenitori, ma il flusso funzionale e` quello reale a step (non lo stub statico).

## 2026-05-01 - UX wizard in modal (riduzione scroll pagina)

- Aggiornata `app/templates/wizard.html`:
  - il flusso wizard viene ora mostrato in un contenitore modale centrato.
  - aggiunto pulsante `Chiudi` verso `/ui/configurations`.
  - aggiunta chiusura rapida con tasto `ESC`.
- Aggiornata `app/static/css/esyy-ui.css`:
  - nuovi stili `wizard-modal-*` (overlay, card, header, progress, body scrollabile interno).
  - ottimizzazione responsive per mobile (`max-height`, padding ridotto).
- Obiettivo raggiunto:
  - i passaggi `Conferma e continua` non costringono piu` a tornare in alto e riscorrere tutta la pagina.
