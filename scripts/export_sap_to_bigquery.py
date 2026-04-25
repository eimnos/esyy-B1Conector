import pandas as pd
import pyodbc
from google.cloud import bigquery
from google.oauth2 import service_account

# =========================
# CONFIGURAZIONE
# =========================
GCP_PROJECT_ID = "vtronik-sap-reporting-cliente"
BQ_DATASET = "sap_reporting"
BQ_TABLE = "stato_ordini_cliente"
BQ_LOCATION = "EU"

SERVICE_ACCOUNT_FILE = r"C:\BigQuery\vtronik-sap-reporting-cliente-72be47a65bcb.json"

SQL_SERVER = r"WIN-NSICHQOT7RV\MSSQL2019"
SQL_DATABASE = "SBO2640_VTK"
SQL_VIEW = "dbo.vw_reporting_stato_ordini_cliente"

SQL_QUERY = f"SELECT * FROM {SQL_VIEW};"

# IMPORTANTE:
# Sostituisci METTI_QUI_LA_TUA_PASSWORD_SA con la password reale di sa
SQL_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DATABASE};"
    "UID=sa;"
    "PWD=manager;"
    "Encrypt=no;"
    "TrustServerCertificate=yes;"
)

# =========================
# SCHEMA BIGQUERY
# =========================
SCHEMA = [
    bigquery.SchemaField("wo_entry", "INT64"),
    bigquery.SchemaField("wo_numero", "INT64"),
    bigquery.SchemaField("ov_entry", "INT64"),
    bigquery.SchemaField("ov_numero", "INT64"),
    bigquery.SchemaField("wo_data_fine_produzione", "DATE"),
    bigquery.SchemaField("ov_data_consegna", "DATE"),
    bigquery.SchemaField("ov_codice_articolo", "STRING"),
    bigquery.SchemaField("ov_descrizione_articolo", "STRING"),
    bigquery.SchemaField("ov_codice_articolo_cliente", "STRING"),
    bigquery.SchemaField("ov_descrizione_articolo_cliente", "STRING"),
    bigquery.SchemaField("ov_quantita_ordinata", "FLOAT64"),
    bigquery.SchemaField("wo_data_inizio_produzione", "DATE"),
    bigquery.SchemaField("ov_data_ordine", "DATE"),
    bigquery.SchemaField("wo_quantita_pianificata", "FLOAT64"),
    bigquery.SchemaField("wo_quantita_completata", "FLOAT64"),
    bigquery.SchemaField("ov_codice_cliente", "STRING"),
    bigquery.SchemaField("ov_nome_cliente", "STRING"),
    bigquery.SchemaField("ddt_quantita_consegnata", "FLOAT64"),
    bigquery.SchemaField("ddt_quantita_residua", "FLOAT64"),
    bigquery.SchemaField("stato_produzione", "STRING"),
    bigquery.SchemaField("stato_spedizione", "STRING"),
]

# =========================
# COLONNE PER CONVERSIONE TIPI
# =========================
DATE_COLUMNS = [
    "wo_data_fine_produzione",
    "ov_data_consegna",
    "wo_data_inizio_produzione",
    "ov_data_ordine",
]

INT_COLUMNS = [
    "wo_entry",
    "wo_numero",
    "ov_entry",
    "ov_numero",
]

FLOAT_COLUMNS = [
    "ov_quantita_ordinata",
    "wo_quantita_pianificata",
    "wo_quantita_completata",
    "ddt_quantita_consegnata",
    "ddt_quantita_residua",
]

STRING_COLUMNS = [
    "ov_codice_articolo",
    "ov_descrizione_articolo",
    "ov_codice_articolo_cliente",
    "ov_descrizione_articolo_cliente",
    "ov_codice_cliente",
    "ov_nome_cliente",
    "stato_produzione",
    "stato_spedizione",
]


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    for col in INT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in FLOAT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    for col in STRING_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype("string")

    return df


def read_sql_data() -> pd.DataFrame:
    print("Connessione a SQL Server...")
    cnxn = pyodbc.connect(SQL_CONN_STR)
    try:
        df = pd.read_sql_query(SQL_QUERY, cnxn)
    finally:
        cnxn.close()

    print(f"Righe estratte: {len(df)}")
    print("Colonne:", list(df.columns))
    return df


def upload_to_bigquery(df: pd.DataFrame) -> None:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE
    )

    client = bigquery.Client(
        project=GCP_PROJECT_ID,
        credentials=credentials
    )

    table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"

    job_config = bigquery.LoadJobConfig(
        schema=SCHEMA,
        write_disposition="WRITE_TRUNCATE"
    )

    print("Tipi dataframe:")
    print(df.dtypes)

    print(f"Caricamento su BigQuery: {table_id}")
    job = client.load_table_from_dataframe(
        df,
        table_id,
        location=BQ_LOCATION,
        job_config=job_config
    )
    job.result()

    table = client.get_table(table_id)
    print(f"Caricamento completato. Righe in tabella: {table.num_rows}")


def main():
    df = read_sql_data()
    df = normalize_dataframe(df)
    upload_to_bigquery(df)


if __name__ == "__main__":
    main()