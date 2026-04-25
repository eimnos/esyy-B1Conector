# Esyy B1Connector — Specifica UX/UI Wizard-Based

**Destinazione file consigliata nel repository:** `docs/ux_ui_wizard_redesign.md`  
**Destinatari:** sviluppatori che lavorano con Codex in Visual Studio Code  
**Stato:** specifica operativa per redesign incrementale dell’interfaccia  
**Prodotto:** Esyy B1Connector  
**Obiettivo:** trasformare l’app da configuratore tecnico a centro di configurazione guidata.

---

## 1. Obiettivo del redesign

L’app deve passare da configuratore tecnico a **centro di configurazione guidata**.

Il flusso funzionale del prodotto rimane:

```text
SAP Business One / SQL Server → View dedicate → Pipeline locale → BigQuery → Looker Studio
```

La UI però non deve presentare subito all’utente concetti tecnici come:

```text
Views
Pipelines
Schedules
ACL
Connection string
Cron
WRITE_TRUNCATE
```

Deve invece presentarli come:

```text
Dati SAP
Sincronizzazione
Pianificazione
Accessi dati
Configurazione BigQuery
Looker Studio
Monitoraggio
```

### Regola principale

Ogni configurazione deve avere:

```text
1. Una card nella homepage/configurazioni
2. Un wizard guidato
3. Un riepilogo leggibile
4. Un test finale
5. Una modifica tramite lo stesso wizard
6. Dettagli tecnici nascosti in Avanzate
```

---

## 2. Direzione grafica approvata

### Layout generale

Usare un layout a due colonne:

```text
┌──────────────────────────────────────────────────────┐
│ Sidebar scura │ Header chiaro                        │
│               ├──────────────────────────────────────│
│               │ Area principale chiara               │
│               │ Card / Wizard / Riepiloghi / Stato   │
└──────────────────────────────────────────────────────┘
```

### Sidebar

La sidebar è il tratto distintivo di Esyy B1Connector.

Colori approvati:

```css
--sidebar-bg: #0B1220;
--sidebar-soft: #111B2E;
--accent: #2563EB;
```

Regole:

- sidebar scura;
- logo Esyy bianco;
- testo bianco/grigio chiaro;
- icone reali nel menu;
- voce attiva con background `rgba(255,255,255,0.10)`;
- bordo/ring leggero sulla voce attiva;
- tenant e versione in basso.

### Area principale

L’area centrale deve restare coerente con lo stile office/professionale di Esyy Flow:

```text
sfondo chiaro
card bianche
bordi sottili
angoli piccoli
ombre leggere
densità professionale
interfaccia office-like
```

Token consigliati:

```css
:root {
  --sidebar-bg: #0B1220;
  --sidebar-soft: #111B2E;
  --accent: #2563EB;
  --app-bg: #F8FAFC;
  --card-bg: #FFFFFF;
  --border: #E2E8F0;
  --text-primary: #0F172A;
  --text-secondary: #64748B;
  --success: #059669;
  --warning: #D97706;
  --danger: #DC2626;
}
```

---

## 3. Menu principale approvato

Menu sidebar:

```text
Panoramica
Configurazioni
Riepiloghi
Monitoraggio
Utenti e accessi
Avanzate
```

Non usare nel menu principale:

```text
Views
Pipelines
Schedules
ACL
Settings
```

Queste voci sono tecniche e devono essere raggiungibili solo da **Avanzate** o tramite i wizard.

---

## 4. Architettura informativa nuova

### 4.1 Panoramica

Prima pagina dopo login.

Deve rispondere a:

```text
Il connettore funziona?
Cosa manca?
Dove devo intervenire?
```

Contenuti minimi:

```text
Stato configurazione: 6/8
Ultima sincronizzazione
Sistema: SAP B1 / BigQuery / Looker / Scheduler
Alert aperti
CTA: Apri configurazioni
CTA: Vedi riepiloghi
```

Card sintetiche:

```text
Stato configurazione
Ultima sincronizzazione
Salute sistema
Alert aperti
```

### 4.2 Configurazioni

Pagina principale dell’app.

Non deve essere una tabella tecnica.  
Deve essere una griglia ordinata di **schede wizard**.

Ordine approvato:

```text
01 Connessione SAP B1
02 Connessione BigQuery
03 Dati SAP da esportare
04 Sincronizzazione
05 Pianificazione
06 Accessi dati clienti
07 Looker Studio
08 Monitoraggio e alert
```

Ogni card deve avere:

```text
icona
numero ordine
titolo
descrizione breve
badge stato
riepilogo configurazione
progress bar
CTA principale
CTA secondaria
```

CTA possibili:

```text
Configura
Modifica con wizard
Risolvi con wizard
Riepilogo
Test configurazione
```

### 4.3 Wizard

Ogni configurazione deve aprirsi come wizard.

Regola:

```text
Anche le modifiche devono avvenire tramite wizard, mai tramite form tecnico libero.
```

Layout wizard:

```text
Torna alle configurazioni
Titolo wizard
Stepper orizzontale
Passo X di Y
Percentuale completamento
Form guidato
Pannello suggerimenti
Pannello dettagli tecnici chiuso
Footer con Indietro / Test / Salva e continua
```

Stepper:

```text
✓ Step completato
● Step attivo
○ Step futuro
⚠ Step con errore
```

### 4.4 Riepiloghi

Pagina di consultazione finale.

Ogni configurazione deve mostrare:

```text
titolo
stato
riepilogo leggibile
progress bar
ultima modifica
pulsante Modifica con wizard
```

La pagina serve anche per:

```text
assistenza
onboarding
collaudo
condivisione configurazione con cliente
```

### 4.5 Monitoraggio

Pagina non configurativa.

Contenuti:

```text
stato SAP B1
stato BigQuery
stato Looker Studio
stato Scheduler
ultime esecuzioni
alert
```

Ogni alert deve avere una CTA leggibile:

```text
Risolvi con wizard
```

Non usare come prima CTA:

```text
Apri log
```

I log tecnici vanno nei dettagli o in Avanzate.

### 4.6 Avanzate

Area tecnica separata.

Contenuti ammessi:

```text
connection string completa
cron manuale
SQL custom
comandi pipeline custom
percorsi file locali
log raw
debug
vecchie pagine tecniche
```

Warning in alto:

```text
Queste impostazioni sono pensate per utenti tecnici. Modifiche errate possono compromettere il funzionamento del connettore.
```

---

## 5. Mapping funzionale vecchio → nuovo

| Funzione attuale | Nuova esposizione UI |
|---|---|
| Views | Dati SAP da esportare |
| Pipelines | Sincronizzazione |
| Schedules | Pianificazione |
| ACL | Accessi dati clienti |
| Settings SQL Server | Wizard Connessione SAP B1 |
| Settings BigQuery | Wizard Connessione BigQuery |
| Run Logs | Monitoraggio |
| App Users | Utenti e accessi |
| Raw config / command | Avanzate |

---

## 6. Stati standard

Usare questi stati ovunque.

```text
completed → Completato
attention → Da verificare
todo → Da configurare
error → Errore
running → In esecuzione
disabled → Disattivato
```

Badge:

| Stato | Colore |
|---|---|
| Completato | verde |
| Da verificare | ambra |
| Da configurare | grigio/blu |
| Errore | rosso |
| In esecuzione | blu |
| Disattivato | grigio |

---

## 7. Wizard da implementare

### 7.1 Wizard — Connessione SAP B1

Step:

```text
1. Tipo database
2. Server e istanza
3. Credenziali
4. Test connessione
5. Conferma
```

Campi principali:

```text
Tipo database: SQL Server / SAP HANA
Server
Istanza opzionale
Porta opzionale
Database company
Metodo autenticazione
Utente
Password
```

Regole UX:

- SAP HANA può essere predisposto, ma indicare se non è ancora completamente supportato;
- connection string completa nascosta in dettagli tecnici;
- warning se l’utente usa `sa`;
- suggerire utente SQL dedicato;
- test connessione obbligatorio prima della conferma.

Warning per `sa`:

```text
Uso di sa sconsigliato.
Per un ambiente stabile è preferibile creare un utente SQL dedicato con accesso solo alle view necessarie.
```

### 7.2 Wizard — Connessione BigQuery

Step:

```text
1. Project ID
2. Dataset
3. Credenziali service account
4. Test permessi
5. Conferma
```

Campi:

```text
Project ID
Dataset
Location
Percorso file credenziali JSON
Tabella default opzionale
```

Azioni:

```text
Test connessione BigQuery
Crea/valida dataset
Conferma configurazione
```

### 7.3 Wizard — Dati SAP da esportare

Step:

```text
1. Modello dati
2. Campi
3. Filtri
4. Anteprima
5. Pubblicazione
```

Regola importante:

Non partire dall’editor SQL.

Prima mostrare modelli guidati:

```text
Ordini cliente e stato produzione
Anagrafiche articoli
Giacenze magazzino
Fatturato
Dataset personalizzato
```

Solo “Dataset personalizzato” apre SQL avanzato.

Anteprima dati prima della pubblicazione:

```text
Anteprima
114 righe trovate
Ultima data consegna: 17/04/2026
Campi data disponibili: ov_data_ordine, ov_data_consegna, wo_data_fine_produzione
```

### 7.4 Wizard — Sincronizzazione

Step:

```text
1. Origine
2. Destinazione
3. Modalità aggiornamento
4. Test run
5. Attiva
```

Tradurre le modalità tecniche:

```text
Sostituisci i dati a ogni aggiornamento
→ WRITE_TRUNCATE

Aggiungi solo nuovi dati
→ WRITE_APPEND

Blocca se la tabella esiste già
→ WRITE_EMPTY
```

Il valore tecnico può essere mostrato in piccolo, sotto all’etichetta utente.

### 7.5 Wizard — Pianificazione

Step:

```text
1. Frequenza
2. Orari
3. Giorni attivi
4. Alert
5. Conferma
```

Non mostrare subito cron.

Frequenze guidate:

```text
Ogni ora
Due volte al giorno
Una volta al giorno
Personalizzata
```

Se l’utente sceglie “Due volte al giorno”:

```text
Mattina: 08:00
Sera: 18:00
```

Cron solo dentro “Personalizzata” o Avanzate.

### 7.6 Wizard — Accessi dati clienti

Step:

```text
1. Utenti
2. Clienti
3. Regole
4. Verifica
5. Attiva filtro Looker
```

Non mostrare `__ALL__` all’utente normale.

Mostrare:

```text
Accesso totale
```

Solo nei dettagli tecnici:

```text
Valore tecnico: __ALL__
```

Tabella leggibile:

```text
Email utente                    Clienti visibili
cliente@azienda.it              C0001, C0002
direzione@azienda.it            Tutti i clienti
```

### 7.7 Wizard — Looker Studio

Step:

```text
1. Sorgente dati BigQuery
2. Campo data principale
3. Filtro email utente
4. Reconnect sorgente
5. Test report
```

Campi data proposti:

```text
ov_data_ordine
ov_data_consegna
wo_data_fine_produzione
```

Warning:

```text
Non usare campi numerici come dimensione data.
```

Microcopy:

```text
Dopo la modifica esegui il reconnect della sorgente dati in Looker Studio.
```

### 7.8 Wizard — Monitoraggio e alert

Step:

```text
1. Controlli
2. Soglie
3. Log
4. Notifiche
5. Verifica
```

Controlli minimi:

```text
ultimo caricamento BigQuery
righe caricate
stato ultimo run
freshness dati
errori pipeline
```

---

## 8. Indicazioni tecniche per il repository attuale

Il progetto attuale usa FastAPI + template HTML/Jinja nel modulo `software_mvp`.

Gli sviluppatori devono lavorare principalmente su:

```text
software_mvp/app/templates/base.html
software_mvp/app/templates/dashboard.html
software_mvp/app/templates/settings.html
software_mvp/app/templates/views_list.html
software_mvp/app/templates/view_detail.html
software_mvp/app/templates/pipelines_list.html
software_mvp/app/templates/pipeline_detail.html
software_mvp/app/templates/schedules.html
software_mvp/app/templates/acl.html
software_mvp/app/templates/users.html
software_mvp/app/ui_routes.py
software_mvp/app/models.py
software_mvp/app/services/*
```

### Strategia consigliata

Non riscrivere tutto in React ora.

Implementare il redesign sopra l’attuale stack:

```text
FastAPI
Jinja templates
CSS condiviso
JS leggero dove serve
```

---

## 9. Nuovi template consigliati

Creare progressivamente:

```text
base.html
overview.html
configurations.html
wizard.html
summaries.html
monitoring.html
users_access.html
advanced_settings.html
```

Mapping:

```text
dashboard.html → overview.html
views_* → gestiti dal wizard Dati SAP
pipelines_* → gestiti dal wizard Sincronizzazione
schedules.html → gestito dal wizard Pianificazione
acl.html → gestito dal wizard Accessi dati
settings.html → spezzato in wizard SAP B1 / BigQuery / Avanzate
```

---

## 10. Route consigliate

```text
GET  /ui/overview
GET  /ui/configurations
GET  /ui/summaries
GET  /ui/monitoring
GET  /ui/users-access
GET  /ui/advanced

GET  /ui/wizard/{wizard_id}
POST /ui/wizard/{wizard_id}/step/{step_id}
POST /ui/wizard/{wizard_id}/test
POST /ui/wizard/{wizard_id}/confirm
```

Per compatibilità, mantenere redirect:

```text
/ui → /ui/overview
/ui/views → /ui/configurations oppure /ui/advanced/views
/ui/pipelines → /ui/configurations oppure /ui/advanced/pipelines
/ui/schedules → /ui/configurations
/ui/acl → /ui/configurations
/ui/settings → /ui/advanced
```

---

## 11. Modello dati UI consigliato

Creare una struttura backend che restituisca alla UI una lista di wizard card.

Esempio Python:

```python
WIZARD_DEFINITIONS = [
    {
        "id": "sap",
        "order": "01",
        "title": "Connessione SAP B1",
        "description": "Collega il database sorgente senza esporre SAP su internet.",
        "status": "completed",
        "progress": 100,
        "current_step": 5,
        "total_steps": 5,
        "summary": "SQL Server · SBODemoIT · utente dedicato consigliato",
        "route": "/ui/wizard/sap",
    },
    {
        "id": "bigquery",
        "order": "02",
        "title": "Connessione BigQuery",
        "description": "Imposta progetto, dataset e service account Google Cloud.",
        "status": "completed",
        "progress": 100,
        "current_step": 5,
        "total_steps": 5,
        "summary": "vtronik-sap-reporting-cliente · sap_reporting · EU",
        "route": "/ui/wizard/bigquery",
    },
]
```

---

## 12. Componenti HTML/CSS da creare

### Sidebar

- logo bianco;
- menu icone;
- tenant card;
- versione app.

### WizardCard

Campi:

```text
icon
order
title
description
status
summary
progress
primary_action
secondary_action
```

### WizardStepper

Campi:

```text
steps
current_step
completed_steps
error_steps
```

### HelpPanel

Pannello laterale wizard:

```text
Suggerimenti
Validazioni
Link guida
Dettagli tecnici compressi
```

### TechnicalDetails

Componente chiuso di default:

```text
Mostra dettagli tecnici
```

Dentro:

```text
connection string
cron
WRITE_TRUNCATE
query SQL
log raw
```

---

## 13. CSS base da creare

File consigliato:

```text
software_mvp/app/static/css/esyy-ui.css
```

Contenuto minimo:

```css
:root {
  --sidebar-bg: #0B1220;
  --sidebar-soft: #111B2E;
  --accent: #2563EB;
  --app-bg: #F8FAFC;
  --card-bg: #FFFFFF;
  --border: #E2E8F0;
  --text-primary: #0F172A;
  --text-secondary: #64748B;
  --success: #059669;
  --warning: #D97706;
  --danger: #DC2626;
}

.app-shell {
  min-height: 100vh;
  display: flex;
  background: var(--app-bg);
  color: var(--text-primary);
}

.sidebar {
  width: 288px;
  background: var(--sidebar-bg);
  color: #fff;
  flex-shrink: 0;
}

.main-area {
  flex: 1;
  min-width: 0;
  background: var(--app-bg);
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.btn-primary {
  background: var(--accent);
  color: white;
  border-radius: 6px;
  padding: 8px 14px;
  font-weight: 500;
}

.btn-secondary {
  background: white;
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 14px;
  font-weight: 500;
}
```

---

## 14. Prompt operativo per Codex — Sprint 1

```text
Obiettivo: implementare il nuovo layout base Esyy B1Connector senza cambiare la logica backend.

Contesto:
Il progetto usa FastAPI + Jinja templates dentro software_mvp.
L’app deve diventare un centro di configurazione guidata.
Mantenere le funzioni esistenti, ma cambiare la navigazione principale.

Task:
1. Aggiorna base.html creando una app shell con sidebar scura (#0B1220), header chiaro e area contenuto.
2. Aggiungi menu principale con icone inline SVG:
   - Panoramica
   - Configurazioni
   - Riepiloghi
   - Monitoraggio
   - Utenti e accessi
   - Avanzate
3. Sposta i link tecnici Views, Pipelines, Schedules, ACL fuori dal menu principale.
4. Crea o aggiorna il file static/css/esyy-ui.css con token e classi base.
5. Mantieni compatibilità con login/logout e ruoli esistenti.
6. Non modificare ancora la logica di esecuzione pipeline, ACL o scheduler.
7. Verifica che tutte le pagine esistenti continuino ad aprirsi senza 500.

Output atteso:
- base.html aggiornato
- CSS condiviso creato/aggiornato
- menu laterale scuro funzionante
- nessuna regressione sulle route esistenti
```

---

## 15. Prompt operativo per Codex — Sprint 2

```text
Obiettivo: creare la pagina Configurazioni con card wizard ordinate.

Task:
1. Crea route GET /ui/configurations.
2. Crea template configurations.html.
3. Nel backend costruisci una lista WIZARD_DEFINITIONS con 8 wizard:
   - sap
   - bigquery
   - data
   - sync
   - schedule
   - access
   - looker
   - monitoring
4. Ogni wizard deve avere:
   - id
   - order
   - title
   - description
   - status
   - progress
   - summary
   - icon
   - route
5. Renderizza una griglia di card.
6. Ogni card deve mostrare:
   - icona
   - numero
   - titolo
   - descrizione
   - badge stato
   - riepilogo
   - progress bar
   - pulsante Configura/Modifica/Risolvi con wizard
7. La route non deve ancora salvare modifiche: solo UI navigabile.
8. Aggiungi redirect o link dal menu Configurazioni alla nuova pagina.

Output atteso:
- /ui/configurations funzionante
- card wizard visibili
- stile coerente con canvas approvato
```

---

## 16. Prompt operativo per Codex — Sprint 3

```text
Obiettivo: creare la struttura generica dei wizard.

Task:
1. Crea route GET /ui/wizard/{wizard_id}.
2. Crea template wizard.html.
3. Implementa un componente Jinja per lo stepper orizzontale.
4. Lo stepper deve mostrare:
   - step completati con check
   - step attivo evidenziato
   - step futuri grigi
   - passo X di Y
   - percentuale completamento
5. A destra del form aggiungi pannello Suggerimenti.
6. Aggiungi pannello Dettagli tecnici chiuso di default.
7. Implementa almeno tre varianti demo:
   - wizard SAP B1
   - wizard Pianificazione
   - wizard Looker Studio
8. Le azioni possono inizialmente essere non persistenti o salvare su app_settings se già disponibile.
9. Non rompere le pagine settings esistenti.

Output atteso:
- /ui/wizard/sap
- /ui/wizard/schedule
- /ui/wizard/looker
- stepper funzionante
- layout form + suggerimenti
```

---

## 17. Prompt operativo per Codex — Sprint 4

```text
Obiettivo: creare la pagina Riepiloghi.

Task:
1. Crea route GET /ui/summaries.
2. Crea template summaries.html.
3. Mostra tutte le configurazioni con:
   - icona
   - titolo
   - stato
   - riepilogo leggibile
   - progress bar
   - ultima modifica se disponibile
   - pulsante Modifica con wizard
4. Il pulsante deve aprire /ui/wizard/{wizard_id}.
5. La pagina deve essere leggibile anche da utenti non tecnici.
6. Non mostrare valori tecnici come __ALL__, WRITE_TRUNCATE o cron come primo livello.

Output atteso:
- /ui/summaries funzionante
- riepiloghi configurazioni coerenti
```

---

## 18. Prompt operativo per Codex — Sprint 5

```text
Obiettivo: creare la nuova pagina Monitoraggio.

Task:
1. Crea route GET /ui/monitoring.
2. Crea template monitoring.html.
3. Mostra card stato:
   - SAP B1
   - BigQuery
   - Looker Studio
   - Scheduler
4. Mostra tabella ultime esecuzioni usando RunLog esistente.
5. Gli errori devono essere mostrati con messaggi user-friendly.
6. Ogni alert deve avere CTA Risolvi con wizard quando possibile.
7. I log raw devono essere accessibili solo da dettagli tecnici.

Output atteso:
- /ui/monitoring funzionante
- tabella run log leggibile
- alert guidati
```

---

## 19. Prompt operativo per Codex — Sprint 6

```text
Obiettivo: riorganizzare le vecchie pagine tecniche.

Task:
1. Rimuovi dal menu principale i link:
   - Views
   - Pipelines
   - Schedules
   - ACL
2. Mantieni le route esistenti per compatibilità.
3. Crea una pagina /ui/advanced.
4. Dentro /ui/advanced inserisci link tecnici:
   - View tecniche
   - Pipeline tecniche
   - Schedule cron
   - ACL raw
   - Settings raw
   - Log tecnici
5. Aggiungi warning in alto:
   “Queste impostazioni sono pensate per utenti tecnici.”
6. Nessuna funzione esistente deve essere eliminata.

Output atteso:
- menu principale semplificato
- funzioni tecniche ancora accessibili da Avanzate
```

---

## 20. Regole di sviluppo da rispettare

### Non fare

```text
Non riscrivere tutto in React.
Non eliminare route esistenti.
Non cambiare logica pipeline durante il redesign UI.
Non mostrare cron, SQL o connection string come primo livello.
Non usare librerie CDN che possono fallire offline.
```

### Fare

```text
Usare lo stack attuale.
Procedere per piccoli sprint.
Verificare ogni sprint con avvio locale.
Mantenere compatibilità con ruoli e login.
Tenere ogni modifica reversibile.
Nascondere dettagli tecnici in pannelli avanzati.
```

---

## 21. Checklist di collaudo per ogni sprint

Dopo ogni modifica Codex, verificare:

```text
Login admin OK
Logout OK
Menu visibile OK
Ruoli rispettati OK
Nessuna pagina 500
Health endpoint OK
CSS caricato OK
Route vecchie ancora accessibili
Nuova pagina responsive almeno desktop/tablet
```

Comandi tipici:

```powershell
cd C:\BigQuery\software_mvp

.\.venv\Scripts\python.exe -m py_compile app\main.py app\ui_routes.py app\models.py

.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Test browser:

```text
http://127.0.0.1:8010/login
http://127.0.0.1:8010/ui/overview
http://127.0.0.1:8010/ui/configurations
http://127.0.0.1:8010/ui/wizard/sap
http://127.0.0.1:8010/ui/summaries
http://127.0.0.1:8010/ui/monitoring
```

---

## 22. Priorità consigliata

Ordine migliore per gli sviluppatori:

```text
1. App shell + sidebar scura
2. Pagina Configurazioni con card wizard
3. Template wizard generico con stepper
4. Wizard SAP B1, BigQuery, Looker, Pianificazione
5. Riepiloghi
6. Monitoraggio
7. Avanzate
8. Collegamento progressivo dei wizard alla logica reale
```

Questa sequenza consente di ottenere subito un risultato visibile senza rischiare di rompere il motore già funzionante.

---

## 23. Nota per Codex / VS Code

Quando si usa Codex in Visual Studio Code, fornire sempre task piccoli e verificabili.

Formato consigliato per ogni prompt:

```text
Contesto:
- stack attuale
- file interessati
- cosa non modificare

Obiettivo:
- risultato specifico dello sprint

Task:
- elenco numerato

Vincoli:
- non rompere route esistenti
- non cambiare logica business
- niente CDN esterne
- mantenere compatibilità login/ruoli

Output atteso:
- file modificati
- route nuove
- test manuali
```

Non chiedere a Codex di “rifare tutta la UI” in un unico prompt.  
Procedere sempre per sprint incrementali.
