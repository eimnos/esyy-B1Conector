from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from google.cloud import bigquery
from google.oauth2 import service_account

# =========================
# CONFIGURAZIONE
# =========================
GCP_PROJECT_ID = "vtronik-sap-reporting-cliente"
BQ_DATASET = "sap_reporting"
BQ_TABLE = "stato_ordini_cliente"
BQ_LOCATION = "EU"
INFORMATION_SCHEMA_REGION = "region-eu"
DEFAULT_THRESHOLD_HOURS = 24

SERVICE_ACCOUNT_FILE = r"C:\BigQuery\vtronik-sap-reporting-cliente-72be47a65bcb.json"
LOCAL_TIMEZONE = "Europe/Rome"


@dataclass
class CheckResult:
    ok: bool
    message: str


def build_client() -> bigquery.Client:
    service_account_file = resolve_service_account_file()
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file
    )
    return bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)


def resolve_service_account_file() -> str:
    default_path = Path(SERVICE_ACCOUNT_FILE)
    if default_path.exists():
        return str(default_path)

    fallback_path = Path(__file__).resolve().parent.parent / default_path.name
    if fallback_path.exists():
        return str(fallback_path)

    return str(default_path)


def to_local_string(value: datetime, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return value.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")


def get_last_load_job(client: bigquery.Client) -> dict | None:
    query = f"""
    SELECT
      creation_time,
      end_time,
      state,
      error_result.message AS error_message
    FROM `{INFORMATION_SCHEMA_REGION}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE job_type = 'LOAD'
      AND destination_table.project_id = @project_id
      AND destination_table.dataset_id = @dataset_id
      AND destination_table.table_id = @table_id
    ORDER BY creation_time DESC
    LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("project_id", "STRING", GCP_PROJECT_ID),
            bigquery.ScalarQueryParameter("dataset_id", "STRING", BQ_DATASET),
            bigquery.ScalarQueryParameter("table_id", "STRING", BQ_TABLE),
        ]
    )

    rows = list(client.query(query, location=BQ_LOCATION, job_config=job_config).result())
    if not rows:
        return None

    row = rows[0]
    return {
        "creation_time": row["creation_time"],
        "end_time": row["end_time"],
        "state": row["state"],
        "error_message": row["error_message"],
    }


def get_table_metadata(client: bigquery.Client) -> dict | None:
    table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
    table = client.get_table(table_id)
    return {
        "last_modified_utc": table.modified,
        "row_count": table.num_rows,
    }


def get_data_max_dates(client: bigquery.Client) -> dict:
    query = f"""
    SELECT
      MAX(ov_data_ordine) AS max_ov_data_ordine,
      MAX(ov_data_consegna) AS max_ov_data_consegna,
      MAX(wo_data_fine_produzione) AS max_wo_data_fine_produzione,
      COUNT(*) AS total_rows
    FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
    """

    row = list(client.query(query, location=BQ_LOCATION).result())[0]
    return {
        "max_ov_data_ordine": row["max_ov_data_ordine"],
        "max_ov_data_consegna": row["max_ov_data_consegna"],
        "max_wo_data_fine_produzione": row["max_wo_data_fine_produzione"],
        "total_rows": row["total_rows"],
    }


def evaluate_freshness(last_load_end: datetime, threshold_hours: int) -> CheckResult:
    now_utc = datetime.now(timezone.utc)
    max_age = timedelta(hours=threshold_hours)
    age = now_utc - last_load_end

    if age > max_age:
        return CheckResult(
            ok=False,
            message=(
                f"Nessun caricamento recente: ultimo LOAD concluso {int(age.total_seconds() // 3600)} ore fa "
                f"(soglia {threshold_hours} ore)."
            ),
        )

    return CheckResult(ok=True, message="Frequenza aggiornamento nei limiti della soglia.")


def is_jobs_permission_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "access denied" in text and "jobs_by_project" in text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Controlla la freschezza della tabella BigQuery con alert su stale data."
    )
    parser.add_argument(
        "--threshold-hours",
        type=int,
        default=DEFAULT_THRESHOLD_HOURS,
        help=f"Soglia massima in ore tra ultimo LOAD e adesso (default: {DEFAULT_THRESHOLD_HOURS}).",
    )
    args = parser.parse_args()

    last_job = None
    used_jobs_history = True

    try:
        client = build_client()
        table_meta = get_table_metadata(client)
    except Exception as exc:
        print(f"[ALERT] Errore durante il controllo BigQuery: {exc}")
        return 1

    if not table_meta:
        print(f"[ALERT] Tabella non trovata: {GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}")
        return 2

    try:
        last_job = get_last_load_job(client)
    except Exception as exc:
        if is_jobs_permission_error(exc):
            used_jobs_history = False
            print(
                "[WARN] Permesso mancante su region-eu.INFORMATION_SCHEMA.JOBS_BY_PROJECT. "
                "Uso fallback su last_modified_time tabella."
            )
        else:
            print(f"[ALERT] Errore durante la lettura dei job LOAD: {exc}")
            return 1

    max_dates = None
    try:
        max_dates = get_data_max_dates(client)
    except Exception as exc:
        print(f"[WARN] Impossibile leggere le max date dei dati: {exc}")

    print(
        f"[INFO] Ultima modifica tabella: {to_local_string(table_meta['last_modified_utc'], LOCAL_TIMEZONE)} "
        f"({LOCAL_TIMEZONE}) | Righe: {table_meta['row_count']}"
    )

    if max_dates:
        print(
            "[INFO] Max date dati: "
            f"ov_data_ordine={max_dates['max_ov_data_ordine']}, "
            f"ov_data_consegna={max_dates['max_ov_data_consegna']}, "
            f"wo_data_fine_produzione={max_dates['max_wo_data_fine_produzione']}, "
            f"righe={max_dates['total_rows']}"
        )

    if last_job:
        last_end = last_job["end_time"] or last_job["creation_time"]
        check = evaluate_freshness(last_end, args.threshold_hours)

        print(
            f"[INFO] Ultimo LOAD avvio: {to_local_string(last_job['creation_time'], LOCAL_TIMEZONE)} "
            f"({LOCAL_TIMEZONE})"
        )
        print(
            f"[INFO] Ultimo LOAD fine:  {to_local_string(last_end, LOCAL_TIMEZONE)} "
            f"({LOCAL_TIMEZONE})"
        )
        print(f"[INFO] Stato job: {last_job['state']}")
        if last_job["error_message"]:
            print(f"[INFO] Errore job: {last_job['error_message']}")

        if last_job["state"] != "DONE" or last_job["error_message"]:
            print("[ALERT] L'ultimo job LOAD risulta non completato correttamente.")
            return 2
    else:
        check = evaluate_freshness(table_meta["last_modified_utc"], args.threshold_hours)
        if used_jobs_history:
            print("[WARN] Nessun job LOAD trovato per la tabella. Uso fallback su metadato tabella.")

    if not check.ok:
        print(f"[ALERT] {check.message}")
        return 2

    if last_job:
        print(f"[OK] {check.message}")
    else:
        print(f"[OK] {check.message} (controllo basato su last_modified_time tabella)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
