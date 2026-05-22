from __future__ import annotations

from copy import deepcopy
from typing import Any


WIZARD_CARD_DEFINITIONS: list[dict[str, str]] = [
    {
        "id": "full",
        "order": "00",
        "title": "Configurazione completa",
        "description": "Percorso guidato end-to-end dalla sorgente SAP a Data Studio.",
        "icon_label": "FULL",
        "technical_route": "/ui/overview",
    },
    {
        "id": "sap",
        "order": "01",
        "title": "Connessione SAP B1",
        "description": "Configura il database sorgente SAP Business One.",
        "icon_label": "SAP",
        "technical_route": "/ui/settings",
    },
    {
        "id": "bigquery",
        "order": "02",
        "title": "Connessione BigQuery",
        "description": "Imposta progetto, dataset e credenziali Google Cloud.",
        "icon_label": "BQ",
        "technical_route": "/ui/settings",
    },
    {
        "id": "data",
        "order": "03",
        "title": "Dati da esportare",
        "description": "Definisci le viste dati da usare nelle esportazioni.",
        "icon_label": "SQL",
        "technical_route": "/ui/views",
    },
    {
        "id": "sync",
        "order": "04",
        "title": "Sincronizzazione",
        "description": "Collega viste e tabelle BigQuery tramite pipeline.",
        "icon_label": "SYNC",
        "technical_route": "/ui/pipelines",
    },
    {
        "id": "schedule",
        "order": "05",
        "title": "Pianificazione",
        "description": "Configura quando eseguire le pipeline in automatico.",
        "icon_label": "CRON",
        "technical_route": "/ui/schedules",
    },
    {
        "id": "access",
        "order": "06",
        "title": "Accessi dati clienti",
        "description": "Definisci i filtri ACL per limitare la visibilita dei dati.",
        "icon_label": "ACL",
        "technical_route": "/ui/acl",
    },
    {
        "id": "looker",
        "order": "07",
        "title": "Data Studio",
        "description": "Genera query sicure per la visualizzazione per utente.",
        "icon_label": "BI",
        "technical_route": "/ui/acl",
    },
    {
        "id": "monitoring",
        "order": "08",
        "title": "Monitoraggio e alert",
        "description": "Controlla esecuzioni, esiti e alert operativi.",
        "icon_label": "OPS",
        "technical_route": "/ui/monitoring",
    },
]


WIZARD_DEFINITIONS: dict[str, dict[str, Any]] = {
    "full": {
        "id": "full",
        "title": "Wizard completo",
        "subtitle": "Configura l'intero connettore in un unico percorso guidato.",
        "steps": [
            {
                "id": "intro",
                "title": "Benvenuto",
                "type": "intro",
                "question": "Vuoi iniziare la configurazione completa?",
                "description": "Questo wizard guida SAP, BigQuery, sincronizzazione, accessi e monitoraggio.",
            },
            {
                "id": "source_engine",
                "title": "Motore sorgente",
                "type": "choice",
                "question": "Quale database usa SAP Business One?",
                "description": "Scegli il motore per adeguare i passaggi successivi.",
                "options": [
                    {"value": "sqlserver", "label": "SQL Server"},
                    {"value": "hana", "label": "SAP HANA"},
                ],
            },
            {
                "id": "tenant",
                "title": "Tenant",
                "type": "input",
                "question": "Quale tenant vuoi configurare?",
                "description": "Usa 'default' se lavori con un solo ambiente.",
                "fields": [
                    {
                        "id": "tenant_code",
                        "label": "Tenant code",
                        "placeholder": "default",
                        "required": True,
                    }
                ],
            },
            {
                "id": "source_target",
                "title": "Sorgente SAP",
                "type": "two_inputs",
                "question": "Indica server e database principale.",
                "description": "Questi dati servono per preparare la connection string.",
                "fields": [
                    {"id": "server", "label": "Server / host", "placeholder": "es. WIN-SERVER01"},
                    {"id": "database", "label": "Database SAP", "placeholder": "es. SBODemoIT"},
                ],
            },
            {
                "id": "source_credentials",
                "title": "Credenziali sorgente",
                "type": "credentials",
                "question": "Inserisci credenziali utente tecnico.",
                "description": "Usa un utente dedicato di sola lettura dove possibile.",
                "fields": [
                    {"id": "username", "label": "Username", "placeholder": "utente_tech"},
                    {
                        "id": "password",
                        "label": "Password",
                        "placeholder": "********",
                        "input_type": "password",
                    },
                ],
            },
            {
                "id": "bq_guide",
                "title": "Preparazione BigQuery",
                "type": "instruction",
                "question": "Esegui la preparazione su Google Cloud.",
                "description": "Passaggi minimi richiesti prima del test automatico.",
                "instructions": [
                    "Abilita BigQuery API sul progetto.",
                    "Crea un service account dedicato.",
                    "Assegna BigQuery Job User e BigQuery Data Editor.",
                    "Salva il file JSON sul server applicativo.",
                ],
            },
            {
                "id": "connections_test",
                "title": "Verifica connessioni",
                "type": "test",
                "question": "Esegui i test e conferma gli esiti.",
                "description": "Segna i test come completati solo dopo verifica reale.",
                "fields": [
                    {
                        "id": "sql_test_result",
                        "label": "Esito test SAP",
                        "input_type": "select",
                        "options": [
                            {"value": "pending", "label": "Da eseguire"},
                            {"value": "ok", "label": "OK"},
                            {"value": "ko", "label": "KO"},
                        ],
                    },
                    {
                        "id": "bq_test_result",
                        "label": "Esito test BigQuery",
                        "input_type": "select",
                        "options": [
                            {"value": "pending", "label": "Da eseguire"},
                            {"value": "ok", "label": "OK"},
                            {"value": "ko", "label": "KO"},
                        ],
                    },
                ],
            },
            {
                "id": "review",
                "title": "Riepilogo finale",
                "type": "review",
                "question": "Confermi i dati raccolti?",
                "description": "Controlla le informazioni prima di passare alla configurazione tecnica dettagliata.",
            },
        ],
    },
    "sap": {
        "id": "sap",
        "title": "Wizard SAP B1",
        "subtitle": "Configura in sequenza la connessione al database SAP.",
        "steps": [
            {
                "id": "intro",
                "title": "Introduzione",
                "type": "intro",
                "question": "Impostiamo la connessione SAP B1?",
                "description": "Il wizard salva una bozza dei dati e prepara la configurazione tecnica.",
            },
            {
                "id": "engine",
                "title": "Motore database",
                "type": "choice",
                "question": "Quale motore usa SAP B1?",
                "description": "Scegli SQL Server o SAP HANA.",
                "options": [
                    {"value": "sqlserver", "label": "SQL Server"},
                    {"value": "hana", "label": "SAP HANA"},
                ],
            },
            {
                "id": "server_and_db",
                "title": "Server e database",
                "type": "two_inputs",
                "question": "Inserisci host e database SAP.",
                "description": "Per SQL Server puoi usare host\\istanza o host,porta.",
                "fields": [
                    {"id": "server", "label": "Server", "placeholder": "es. WIN-APP01\\MSSQL2019"},
                    {"id": "database", "label": "Database", "placeholder": "es. SBODemoIT"},
                ],
            },
            {
                "id": "credentials",
                "title": "Credenziali",
                "type": "credentials",
                "question": "Inserisci utente e password tecnica.",
                "description": "L'utente deve avere permessi di lettura sulle tabelle usate.",
                "fields": [
                    {"id": "uid", "label": "Username", "placeholder": "utente_tech"},
                    {
                        "id": "pwd",
                        "label": "Password",
                        "placeholder": "********",
                        "input_type": "password",
                    },
                ],
            },
            {
                "id": "test",
                "title": "Test connessione",
                "type": "test",
                "question": "Esegui il test e registra l'esito.",
                "description": (
                    "Dalla pagina tecnica puoi lanciare il test reale. "
                    "Per SQL Server il test viene comunque rieseguito automaticamente alla conferma finale."
                ),
                "fields": [
                    {
                        "id": "result",
                        "label": "Esito test",
                        "input_type": "select",
                        "options": [
                            {"value": "pending", "label": "Da eseguire"},
                            {"value": "ok", "label": "OK"},
                            {"value": "ko", "label": "KO"},
                        ],
                    }
                ],
            },
            {
                "id": "review",
                "title": "Conferma",
                "type": "review",
                "question": "Confermi la bozza SAP?",
                "description": "Puoi sempre riaprire il wizard per modificare i dati.",
            },
        ],
    },
    "bigquery": {
        "id": "bigquery",
        "title": "Wizard BigQuery",
        "subtitle": "Definisci progetto, dataset e credenziali Google Cloud.",
        "steps": [
            {
                "id": "intro",
                "title": "Introduzione",
                "type": "intro",
                "question": "Prepariamo la connessione BigQuery?",
                "description": "Il wizard raccoglie i parametri minimi per il setup.",
            },
            {
                "id": "project",
                "title": "Progetto",
                "type": "input",
                "question": "Qual e il Project ID?",
                "description": "Usa l'ID del progetto GCP, non il nome descrittivo.",
                "fields": [
                    {"id": "project_id", "label": "Project ID", "placeholder": "my-project-id"},
                ],
            },
            {
                "id": "dataset_and_location",
                "title": "Dataset",
                "type": "two_inputs",
                "question": "Imposta dataset e location.",
                "description": "Esempio dataset sap_reporting, location EU.",
                "fields": [
                    {"id": "dataset", "label": "Dataset", "placeholder": "sap_reporting"},
                    {"id": "location", "label": "Location", "placeholder": "EU"},
                ],
            },
            {
                "id": "credentials",
                "title": "Credenziali JSON",
                "type": "input",
                "question": "Dove si trova il file JSON del service account?",
                "description": "Percorso locale del server che esegue l'app.",
                "fields": [
                    {
                        "id": "credentials_path",
                        "label": "Path JSON",
                        "placeholder": "C:\\BigQuery\\service_account.json",
                    },
                ],
            },
            {
                "id": "review",
                "title": "Conferma",
                "type": "review",
                "question": "Confermi i dati BigQuery?",
                "description": "Salva la bozza e applica dal pannello tecnico.",
            },
        ],
    },
    "data": {
        "id": "data",
        "title": "Wizard Dati SAP",
        "subtitle": "Imposta cosa esportare e con quale granularita.",
        "steps": [
            {
                "id": "intro",
                "title": "Introduzione",
                "type": "intro",
                "question": "Configuriamo le view dati?",
                "description": "Scegli l'area principale e poi passa alla pagina view tecniche.",
            },
            {
                "id": "scope",
                "title": "Area dati",
                "type": "choice",
                "question": "Qual e l'area prioritaria?",
                "description": "Puoi creare piu viste anche in momenti successivi.",
                "options": [
                    {"value": "ordini", "label": "Ordini cliente"},
                    {"value": "produzione", "label": "Produzione"},
                    {"value": "magazzino", "label": "Magazzino"},
                ],
            },
            {
                "id": "review",
                "title": "Conferma",
                "type": "review",
                "question": "Confermi il perimetro dati?",
                "description": "Apri poi la pagina Views per costruire la query.",
            },
        ],
    },
    "sync": {
        "id": "sync",
        "title": "Wizard Sincronizzazione",
        "subtitle": "Configura la pipeline che carica dati da SAP a BigQuery.",
        "steps": [
            {
                "id": "intro",
                "title": "Introduzione",
                "type": "intro",
                "question": "Procediamo con la pipeline?",
                "description": "Collegherai una view sorgente a una tabella BigQuery.",
            },
            {
                "id": "pipeline_identity",
                "title": "Identita pipeline",
                "type": "two_inputs",
                "question": "Come vuoi chiamare questa pipeline?",
                "description": "Usa un nome operativo chiaro per riconoscerla nei run.",
                "fields": [
                    {"id": "tenant_code", "label": "Tenant code", "placeholder": "default", "required": True},
                    {
                        "id": "name",
                        "label": "Nome pipeline",
                        "placeholder": "export_ordini_clienti",
                        "required": True,
                    },
                ],
            },
            {
                "id": "source_view",
                "title": "View sorgente",
                "type": "input",
                "question": "Quale view SAP vuoi esportare?",
                "description": "Seleziona una view gia creata nella sezione Dati da esportare.",
                "fields": [
                    {
                        "id": "source_view_id",
                        "label": "View sorgente",
                        "input_type": "select",
                        "required": True,
                        "options": [],
                    }
                ],
            },
            {
                "id": "pipeline_target",
                "title": "Target BigQuery",
                "type": "two_inputs",
                "question": "Dove vuoi caricare i dati su BigQuery?",
                "description": "Dataset e tabella di destinazione della pipeline.",
                "fields": [
                    {"id": "bq_dataset", "label": "BigQuery dataset", "placeholder": "sap_reporting", "required": True},
                    {
                        "id": "bq_table",
                        "label": "BigQuery table",
                        "placeholder": "stato_ordini_cliente",
                        "required": True,
                    },
                ],
            },
            {
                "id": "write_mode",
                "title": "Modalita di scrittura",
                "type": "choice",
                "question": "Quale write mode vuoi usare?",
                "description": "WRITE_TRUNCATE sostituisce i dati, WRITE_APPEND li accoda.",
                "options": [
                    {"value": "WRITE_TRUNCATE", "label": "WRITE_TRUNCATE"},
                    {"value": "WRITE_APPEND", "label": "WRITE_APPEND"},
                    {"value": "WRITE_EMPTY", "label": "WRITE_EMPTY"},
                ],
            },
            {
                "id": "review",
                "title": "Conferma",
                "type": "review",
                "question": "Confermi i parametri pipeline?",
                "description": "Alla conferma finale la pipeline viene creata o aggiornata automaticamente.",
            },
        ],
    },
    "schedule": {
        "id": "schedule",
        "title": "Wizard Pianificazione",
        "subtitle": "Definisci quando eseguire automaticamente le pipeline.",
        "steps": [
            {
                "id": "intro",
                "title": "Introduzione",
                "type": "intro",
                "question": "Attiviamo la pianificazione?",
                "description": "Configura cron e timezone in modalita guidata.",
            },
            {
                "id": "pipeline",
                "title": "Pipeline",
                "type": "input",
                "question": "Quale pipeline vuoi pianificare?",
                "description": "Seleziona la pipeline su cui applicare il cron.",
                "fields": [
                    {
                        "id": "pipeline_id",
                        "label": "Pipeline",
                        "input_type": "select",
                        "required": True,
                        "options": [],
                    }
                ],
            },
            {
                "id": "timing",
                "title": "Cron e timezone",
                "type": "two_inputs",
                "question": "Quando deve partire la sincronizzazione?",
                "description": "Formato cron a 5 campi + timezone.",
                "fields": [
                    {"id": "cron_expression", "label": "Cron (5 campi)", "placeholder": "0 * * * *", "required": True},
                    {
                        "id": "timezone",
                        "label": "Timezone",
                        "input_type": "select",
                        "required": True,
                        "options": [],
                    },
                ],
            },
            {
                "id": "active",
                "title": "Stato schedule",
                "type": "choice",
                "question": "Vuoi attivare subito la schedule?",
                "description": "Puoi comunque modificare lo stato in seguito.",
                "options": [
                    {"value": "yes", "label": "Attiva"},
                    {"value": "no", "label": "Disattiva"},
                ],
            },
            {
                "id": "review",
                "title": "Conferma",
                "type": "review",
                "question": "Confermi i parametri della schedule?",
                "description": "Alla conferma finale la schedule viene creata o aggiornata automaticamente.",
            },
        ],
    },
    "access": {
        "id": "access",
        "title": "Wizard Accessi dati",
        "subtitle": "Imposta ACL utente-campo per limitare la visibilita in Data Studio.",
        "steps": [
            {
                "id": "intro",
                "title": "Introduzione",
                "type": "intro",
                "question": "Configuriamo i filtri accesso?",
                "description": "Il wizard prepara regole prima della gestione tecnica ACL.",
            },
            {
                "id": "mode",
                "title": "Modalita regole",
                "type": "choice",
                "question": "Che tipo di regole vuoi usare?",
                "description": "Legacy customer_code o filtri generici multi-campo.",
                "options": [
                    {"value": "legacy", "label": "ACL legacy customer_code"},
                    {"value": "generic", "label": "ACL filtri generici"},
                ],
            },
            {
                "id": "review",
                "title": "Conferma",
                "type": "review",
                "question": "Confermi modalita ACL?",
                "description": "Continua nella pagina ACL per inserire le regole.",
            },
        ],
    },
    "looker": {
        "id": "looker",
        "title": "Wizard Data Studio",
        "subtitle": "Prepara la query filtrata per utente e la pubblicazione report.",
        "steps": [
            {
                "id": "intro",
                "title": "Introduzione",
                "type": "intro",
                "question": "Configuriamo Data Studio?",
                "description": "Il wizard guida i prerequisiti per report sicuri.",
            },
            {
                "id": "instruction",
                "title": "Istruzioni operative",
                "type": "instruction",
                "question": "Passaggi da completare in Data Studio.",
                "description": "Sequenza minima consigliata.",
                "instructions": [
                    "Crea nuova sorgente dati BigQuery.",
                    "Usa la query generata con parametro @DS_USER_EMAIL.",
                    "Imposta credenziali viewer.",
                    "Verifica con un utente non master.",
                ],
            },
            {
                "id": "review",
                "title": "Conferma",
                "type": "review",
                "question": "Confermi la checklist Data Studio?",
                "description": "In caso di dubbi usa la guida ACL/Data Studio.",
            },
        ],
    },
    "monitoring": {
        "id": "monitoring",
        "title": "Wizard Monitoraggio",
        "subtitle": "Definisci il livello di controllo operativo e alert.",
        "steps": [
            {
                "id": "intro",
                "title": "Introduzione",
                "type": "intro",
                "question": "Impostiamo il monitoraggio?",
                "description": "Scegli frequenza controllo e canale operativo.",
            },
            {
                "id": "mode",
                "title": "Livello monitoraggio",
                "type": "choice",
                "question": "Quale livello preferisci?",
                "description": "Base controlla esiti, avanzato include alert mirati.",
                "options": [
                    {"value": "base", "label": "Base"},
                    {"value": "advanced", "label": "Avanzato"},
                ],
            },
            {
                "id": "review",
                "title": "Conferma",
                "type": "review",
                "question": "Confermi il profilo monitoraggio?",
                "description": "Gestirai poi i dettagli nella pagina Monitoraggio.",
            },
        ],
    },
}


def list_wizard_card_definitions() -> list[dict[str, str]]:
    return deepcopy(WIZARD_CARD_DEFINITIONS)


def get_wizard_definition(wizard_id: str) -> dict[str, Any] | None:
    payload = WIZARD_DEFINITIONS.get((wizard_id or "").strip().lower())
    if not payload:
        return None
    return deepcopy(payload)
