from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pyodbc
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ACLFilterRule, ACLRule, AppSetting, Pipeline, ReportView
from .sqlserver_service import SQLServerPublishError, get_effective_sqlserver_conn_str

BQ_PROJECT_ID_SETTING_KEY = "bq_project_id"
BQ_DATASET_SETTING_KEY = "bq_default_dataset"
BQ_TABLE_SETTING_KEY = "bq_default_table"
BQ_LOCATION_SETTING_KEY = "bq_location"
BQ_CREDENTIALS_FILE_SETTING_KEY = "bq_credentials_file"
BQ_ACL_TABLE_DEFAULT = "acl_utenti_clienti"
BQ_ACL_FILTER_TABLE_DEFAULT = "acl_filter_rules"

VALID_WRITE_DISPOSITIONS = {"WRITE_TRUNCATE", "WRITE_APPEND", "WRITE_EMPTY"}


class BigQueryServiceError(Exception):
    pass


@dataclass(frozen=True)
class BigQueryRuntimeConfig:
    project_id: str
    dataset: str
    table: str
    location: str
    credentials_file: str


@dataclass(frozen=True)
class ManagedLoadResult:
    rows_extracted: int
    rows_loaded: int
    message: str


def _load_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppSetting, key)
    if not row:
        return default
    return (row.value or "").strip() or default


def _clean_ref(value: str | None) -> str:
    return (value or "").strip().strip("`")


def _split_project_dataset(raw: str) -> tuple[str | None, str]:
    value = _clean_ref(raw)
    if not value:
        return None, ""
    if ":" in value:
        project, dataset = value.split(":", 1)
        return _clean_ref(project), _clean_ref(dataset)
    if value.count(".") == 1:
        project, dataset = value.split(".", 1)
        return _clean_ref(project), _clean_ref(dataset)
    return None, value


def _split_table_ref(raw: str) -> tuple[str | None, str | None, str]:
    value = _clean_ref(raw)
    if not value:
        return None, None, ""
    if ":" in value and "." in value:
        project, rest = value.split(":", 1)
        dataset, table = rest.split(".", 1)
        return _clean_ref(project), _clean_ref(dataset), _clean_ref(table)
    if value.count(".") == 2:
        project, dataset, table = value.split(".", 2)
        return _clean_ref(project), _clean_ref(dataset), _clean_ref(table)
    if value.count(".") == 1:
        dataset, table = value.split(".", 1)
        return None, _clean_ref(dataset), _clean_ref(table)
    return None, None, value


def _normalize_target(project_id: str, dataset: str, table: str = "") -> tuple[str, str, str]:
    project = _clean_ref(project_id)
    ds = _clean_ref(dataset)
    tb = _clean_ref(table)

    parsed_project, parsed_dataset = _split_project_dataset(ds)
    if parsed_project:
        project = parsed_project
    ds = parsed_dataset

    table_project, table_dataset, table_name = _split_table_ref(tb)
    if table_project:
        project = table_project
    if table_dataset:
        ds = table_dataset
    if table_name:
        tb = table_name

    return project, ds, tb


def get_runtime_config(db: Session) -> BigQueryRuntimeConfig:
    project_id = _load_setting(db, BQ_PROJECT_ID_SETTING_KEY, settings.bq_project_id).strip()
    dataset = _load_setting(db, BQ_DATASET_SETTING_KEY, settings.bq_default_dataset).strip()
    table = _load_setting(db, BQ_TABLE_SETTING_KEY, settings.bq_default_table).strip()
    location = _load_setting(db, BQ_LOCATION_SETTING_KEY, settings.bq_location).strip() or "EU"
    credentials_file = _load_setting(db, BQ_CREDENTIALS_FILE_SETTING_KEY, settings.bq_credentials_file).strip()
    return BigQueryRuntimeConfig(
        project_id=project_id,
        dataset=dataset,
        table=table,
        location=location,
        credentials_file=credentials_file,
    )


def _import_bigquery_modules():
    try:
        from google.cloud import bigquery
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover
        raise BigQueryServiceError(
            "Dipendenze BigQuery mancanti. Installa: google-cloud-bigquery google-auth"
        ) from exc
    return bigquery, service_account


def _build_bigquery_client(config: BigQueryRuntimeConfig):
    bigquery, service_account = _import_bigquery_modules()

    project_id = config.project_id
    credentials = None
    if config.credentials_file:
        file_path = Path(config.credentials_file)
        if not file_path.exists():
            raise BigQueryServiceError(f"File credenziali non trovato: {file_path}")
        credentials = service_account.Credentials.from_service_account_file(str(file_path))
        if not project_id:
            project_id = credentials.project_id or ""

    if not project_id:
        raise BigQueryServiceError(
            "Project ID BigQuery non configurato. Imposta BQ project in Settings o in .env."
        )

    client = bigquery.Client(project=project_id, credentials=credentials)
    return bigquery, client, project_id


def test_connection(
    db: Session,
    *,
    project_id: str | None = None,
    dataset: str | None = None,
    location: str | None = None,
    credentials_file: str | None = None,
) -> tuple[str, str]:
    config = get_runtime_config(db)
    merged = BigQueryRuntimeConfig(
        project_id=(project_id or "").strip() or config.project_id,
        dataset=(dataset or "").strip() or config.dataset,
        table=config.table,
        location=(location or "").strip() or config.location,
        credentials_file=(credentials_file or "").strip() or config.credentials_file,
    )
    normalized_project, normalized_dataset, _ = _normalize_target(
        merged.project_id,
        merged.dataset,
        "",
    )
    normalized = BigQueryRuntimeConfig(
        project_id=normalized_project,
        dataset=normalized_dataset,
        table=merged.table,
        location=merged.location,
        credentials_file=merged.credentials_file,
    )

    _, client, effective_project = _build_bigquery_client(normalized)
    if normalized.dataset:
        ds_ref = f"{effective_project}.{normalized.dataset}"
        try:
            client.get_dataset(ds_ref)
            return effective_project, f"Dataset trovato: {ds_ref}"
        except Exception:
            return effective_project, f"Connessione OK. Dataset non trovato: {ds_ref}"
    return effective_project, "Connessione OK."


def ensure_dataset(
    db: Session,
    *,
    project_id: str | None = None,
    dataset: str | None = None,
    location: str | None = None,
    credentials_file: str | None = None,
) -> str:
    config = get_runtime_config(db)
    merged = BigQueryRuntimeConfig(
        project_id=(project_id or "").strip() or config.project_id,
        dataset=(dataset or "").strip() or config.dataset,
        table=config.table,
        location=(location or "").strip() or config.location,
        credentials_file=(credentials_file or "").strip() or config.credentials_file,
    )
    normalized_project, normalized_dataset, _ = _normalize_target(
        merged.project_id,
        merged.dataset,
        "",
    )
    if not normalized_dataset:
        raise BigQueryServiceError("Dataset BigQuery non configurato.")
    normalized = BigQueryRuntimeConfig(
        project_id=normalized_project,
        dataset=normalized_dataset,
        table=merged.table,
        location=merged.location,
        credentials_file=merged.credentials_file,
    )

    bigquery, client, effective_project = _build_bigquery_client(normalized)
    dataset_ref = bigquery.Dataset(f"{effective_project}.{normalized.dataset}")
    dataset_ref.location = normalized.location
    client.create_dataset(dataset_ref, exists_ok=True)
    return f"{effective_project}.{normalized.dataset}"


def _serialize_value(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _extract_rows_from_sql(view: ReportView) -> tuple[int, list[dict]]:
    conn_str = get_effective_sqlserver_conn_str()
    if not conn_str:
        raise SQLServerPublishError(
            "Connessione SQL Server non configurata. Impostala in Settings o nel file .env."
        )

    query = (view.select_sql or "").strip()
    if not query:
        query = f"SELECT * FROM [{view.schema_name}].[{view.view_name}]"
    if query.endswith(";"):
        query = query[:-1]

    try:
        cnxn = pyodbc.connect(conn_str, timeout=20)
        try:
            cursor = cnxn.cursor()
            cursor.execute(query)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            rows = []
            for record in cursor.fetchall():
                payload = {col: _serialize_value(val) for col, val in zip(columns, record)}
                rows.append(payload)
            return len(rows), rows
        finally:
            cnxn.close()
    except pyodbc.Error as exc:
        raise BigQueryServiceError(f"Errore lettura SQL Server: {exc}") from exc


def run_pipeline_sql_to_bigquery(db: Session, pipeline: Pipeline, view: ReportView) -> ManagedLoadResult:
    config = get_runtime_config(db)
    dataset = (pipeline.bq_dataset or "").strip() or config.dataset
    table = (pipeline.bq_table or "").strip() or config.table
    location = config.location
    project_id, dataset, table = _normalize_target(config.project_id, dataset, table)

    if not dataset:
        raise BigQueryServiceError("Dataset BigQuery non configurato (pipeline/settings).")
    if not table:
        raise BigQueryServiceError("Tabella BigQuery non configurata (pipeline/settings).")

    normalized_cfg = BigQueryRuntimeConfig(
        project_id=project_id,
        dataset=dataset,
        table=table,
        location=location,
        credentials_file=config.credentials_file,
    )
    bigquery, client, effective_project = _build_bigquery_client(normalized_cfg)
    ensure_dataset(
        db,
        project_id=effective_project,
        dataset=dataset,
        location=location,
        credentials_file=config.credentials_file,
    )

    rows_extracted, rows = _extract_rows_from_sql(view)
    if rows_extracted == 0:
        return ManagedLoadResult(
            rows_extracted=0,
            rows_loaded=0,
            message=(
                f"Managed mode OK: nessuna riga estratta dalla query della view "
                f"{view.schema_name}.{view.view_name}."
            ),
        )

    write_mode = (pipeline.write_mode or "WRITE_TRUNCATE").strip().upper()
    if write_mode not in VALID_WRITE_DISPOSITIONS:
        write_mode = "WRITE_TRUNCATE"

    table_id = f"{effective_project}.{dataset}.{table}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=write_mode,
        autodetect=True,
    )
    try:
        job = client.load_table_from_json(
            rows,
            table_id,
            location=location,
            job_config=job_config,
        )
        job.result()
    except Exception as exc:
        raise BigQueryServiceError(f"Errore caricamento BigQuery: {exc}") from exc

    return ManagedLoadResult(
        rows_extracted=rows_extracted,
        rows_loaded=rows_extracted,
        message=(
            f"Managed mode OK: {rows_extracted} righe caricate su {table_id} "
            f"(write_mode={write_mode}, location={location})."
        ),
    )


def _ensure_acl_table(bigquery, client, *, project_id: str, dataset: str, table: str) -> str:
    table_id = f"{project_id}.{dataset}.{table}"
    schema = [
        bigquery.SchemaField("tenant_code", "STRING"),
        bigquery.SchemaField("user_email", "STRING"),
        bigquery.SchemaField("ov_codice_cliente", "STRING"),
        bigquery.SchemaField("is_active", "BOOL"),
        bigquery.SchemaField("note", "STRING"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
        bigquery.SchemaField("updated_at", "TIMESTAMP"),
    ]
    table_ref = bigquery.Table(table_id, schema=schema)
    client.create_table(table_ref, exists_ok=True)
    return table_id


def _ensure_acl_filter_table(bigquery, client, *, project_id: str, dataset: str, table: str) -> str:
    table_id = f"{project_id}.{dataset}.{table}"
    schema = [
        bigquery.SchemaField("tenant_code", "STRING"),
        bigquery.SchemaField("view_name", "STRING"),
        bigquery.SchemaField("user_email", "STRING"),
        bigquery.SchemaField("field_name", "STRING"),
        bigquery.SchemaField("operator", "STRING"),
        bigquery.SchemaField("field_value", "STRING"),
        bigquery.SchemaField("is_master", "BOOL"),
        bigquery.SchemaField("is_active", "BOOL"),
        bigquery.SchemaField("note", "STRING"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
        bigquery.SchemaField("updated_at", "TIMESTAMP"),
    ]
    table_ref = bigquery.Table(table_id, schema=schema)
    client.create_table(table_ref, exists_ok=True)
    return table_id


def _get_existing_bq_fields(client, table_id: str) -> set[str]:
    try:
        table_obj = client.get_table(table_id)
    except Exception:
        return set()
    return {str(col.name).lower() for col in table_obj.schema}


def _truncate_table(client, table_id: str, location: str) -> None:
    client.query(f"TRUNCATE TABLE `{table_id}`", location=location).result()


def _sync_json_rows_to_table(
    *,
    bigquery,
    client,
    table_id: str,
    location: str,
    rows_payload: list[dict],
) -> None:
    if not rows_payload:
        _truncate_table(client, table_id, location)
        return
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        autodetect=False,
    )
    job = client.load_table_from_json(
        rows_payload,
        table_id,
        location=location,
        job_config=job_config,
    )
    job.result()


def sync_acl_rules_to_bigquery(
    db: Session,
    *,
    table_name: str = BQ_ACL_TABLE_DEFAULT,
) -> str:
    config = get_runtime_config(db)
    project_id, dataset, _ = _normalize_target(config.project_id, config.dataset, "")
    if not dataset:
        raise BigQueryServiceError("Dataset BigQuery non configurato: impossibile sincronizzare ACL.")

    normalized_cfg = BigQueryRuntimeConfig(
        project_id=project_id,
        dataset=dataset,
        table=table_name,
        location=config.location,
        credentials_file=config.credentials_file,
    )
    bigquery, client, effective_project = _build_bigquery_client(normalized_cfg)
    ensure_dataset(
        db,
        project_id=effective_project,
        dataset=dataset,
        location=config.location,
        credentials_file=config.credentials_file,
    )
    table_id = _ensure_acl_table(
        bigquery,
        client,
        project_id=effective_project,
        dataset=dataset,
        table=table_name,
    )

    existing_fields = _get_existing_bq_fields(client, table_id)

    rows_db = (
        db.query(ACLRule)
        .order_by(ACLRule.tenant_code.asc(), ACLRule.user_email.asc(), ACLRule.customer_code.asc())
        .all()
    )
    rows_payload: list[dict] = []
    for row in rows_db:
        try:
            payload = {
                "tenant_code": row.tenant_code,
                "user_email": (row.user_email or "").lower().strip(),
                "ov_codice_cliente": row.customer_code,
                "customer_code": row.customer_code,  # compatibilita con eventuali tabelle legacy
                "is_active": bool(row.is_active),
                "note": row.note,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            if existing_fields:
                payload = {k: v for k, v in payload.items() if k.lower() in existing_fields}
            rows_payload.append(payload)
        except Exception as exc:
            raise BigQueryServiceError(f"Errore preparazione payload ACL: {exc}") from exc

    try:
        _sync_json_rows_to_table(
            bigquery=bigquery,
            client=client,
            table_id=table_id,
            location=config.location,
            rows_payload=rows_payload,
        )
    except Exception as exc:
        raise BigQueryServiceError(f"Errore sincronizzazione ACL su BigQuery: {exc}") from exc

    return f"ACL sincronizzata su {table_id}. Righe caricate: {len(rows_payload)}"


def sync_acl_filter_rules_to_bigquery(
    db: Session,
    *,
    table_name: str = BQ_ACL_FILTER_TABLE_DEFAULT,
) -> str:
    config = get_runtime_config(db)
    project_id, dataset, _ = _normalize_target(config.project_id, config.dataset, "")
    if not dataset:
        raise BigQueryServiceError("Dataset BigQuery non configurato: impossibile sincronizzare ACL filtri.")

    normalized_cfg = BigQueryRuntimeConfig(
        project_id=project_id,
        dataset=dataset,
        table=table_name,
        location=config.location,
        credentials_file=config.credentials_file,
    )
    bigquery, client, effective_project = _build_bigquery_client(normalized_cfg)
    ensure_dataset(
        db,
        project_id=effective_project,
        dataset=dataset,
        location=config.location,
        credentials_file=config.credentials_file,
    )
    table_id = _ensure_acl_filter_table(
        bigquery,
        client,
        project_id=effective_project,
        dataset=dataset,
        table=table_name,
    )
    existing_fields = _get_existing_bq_fields(client, table_id)

    rows_db = (
        db.query(ACLFilterRule, ReportView)
        .join(ReportView, ReportView.id == ACLFilterRule.view_id)
        .order_by(
            ACLFilterRule.tenant_code.asc(),
            ACLFilterRule.view_id.asc(),
            ACLFilterRule.user_email.asc(),
            ACLFilterRule.field_name.asc(),
        )
        .all()
    )
    rows_payload: list[dict] = []
    for rule, view in rows_db:
        payload = {
            "tenant_code": rule.tenant_code,
            "view_name": view.view_name,
            "user_email": (rule.user_email or "").lower().strip(),
            "field_name": rule.field_name,
            "operator": rule.operator,
            "field_value": rule.field_value,
            "is_master": bool(rule.is_master),
            "is_active": bool(rule.is_active),
            "note": rule.note,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
        }
        if existing_fields:
            payload = {k: v for k, v in payload.items() if k.lower() in existing_fields}
        rows_payload.append(payload)

    try:
        _sync_json_rows_to_table(
            bigquery=bigquery,
            client=client,
            table_id=table_id,
            location=config.location,
            rows_payload=rows_payload,
        )
    except Exception as exc:
        raise BigQueryServiceError(f"Errore sincronizzazione ACL filtri su BigQuery: {exc}") from exc

    return f"ACL filtri sincronizzata su {table_id}. Righe caricate: {len(rows_payload)}"
