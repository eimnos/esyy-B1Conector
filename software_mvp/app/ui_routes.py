from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .deps import get_db
from .models import ACLFilterRule, ACLRule, AppSetting, AppUser, Pipeline, ReportView, RunLog, Schedule
from .services.auth_service import (
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    authenticate_user,
    hash_password,
    normalize_role,
)
from .services.bigquery_service import (
    BQ_ACL_FILTER_TABLE_DEFAULT,
    BQ_CREDENTIALS_FILE_SETTING_KEY,
    BQ_DATASET_SETTING_KEY,
    BQ_LOCATION_SETTING_KEY,
    BQ_PROJECT_ID_SETTING_KEY,
    BQ_TABLE_SETTING_KEY,
    BigQueryServiceError,
    ensure_dataset,
    sync_acl_filter_rules_to_bigquery,
    sync_acl_rules_to_bigquery,
    test_connection as test_bigquery_connection,
)
from .services.pipeline_service import run_pipeline
from .services.scheduler_service import reload_jobs, validate_cron_expression
from .services.sqlserver_service import (
    SQLSERVER_CONN_STR_SETTING_KEY,
    SQLServerPublishError,
    publish_view,
    test_sqlserver_connection,
)
from .services.wizard_definitions import get_wizard_definition, list_wizard_card_definitions
from .services.wizard_session_service import (
    WIZARD_STATUS_COMPLETED,
    WIZARD_STATUS_IN_PROGRESS,
    WIZARD_STATUS_NOT_STARTED,
    WIZARD_STATUS_READY_TO_CONFIRM,
    WIZARD_STATUS_TEST_FAILED,
    WIZARD_STATUS_WAITING_EXTERNAL_ACTION,
    calculate_progress,
    get_or_create_session,
    get_session,
    mark_completed,
    move_back,
    move_next,
    move_to_step,
    read_draft_data,
    required_step_missing_fields,
    save_step_data,
    set_test_result,
)

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
SOURCE_DB_ENGINE_SETTING_KEY = "source_db_engine"
HANA_CONN_STR_SETTING_KEY = "hana_conn_str"
MASTER_CUSTOMER_CODE = "__ALL__"
WIZARD_DRAFTS_SESSION_KEY = "wizard_drafts"
SCHEDULE_TIMEZONE_OPTIONS = [
    "Europe/Rome",
    "UTC",
    "Europe/London",
    "Europe/Paris",
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Shanghai",
]
ACL_FILTER_OPERATORS = [
    ("EQ", "="),
    ("NE", "<>"),
    ("CONTAINS", "CONTAINS"),
    ("STARTS_WITH", "STARTS_WITH"),
    ("ENDS_WITH", "ENDS_WITH"),
    ("IN", "IN (csv)"),
    ("GT", ">"),
    ("GTE", ">="),
    ("LT", "<"),
    ("LTE", "<="),
]
ACL_FILTER_OPERATOR_KEYS = {key for key, _ in ACL_FILTER_OPERATORS}


def _redirect(
    path: str,
    message: str | None = None,
    error: str | None = None,
    *,
    message_scope: str | None = None,
    error_scope: str | None = None,
) -> RedirectResponse:
    params: dict[str, str] = dict(parse_qsl(urlsplit(path).query))
    if message:
        params["message"] = message
    if error:
        params["error"] = error
    if message_scope:
        params["message_scope"] = message_scope
    if error_scope:
        params["error_scope"] = error_scope
    parts = urlsplit(path)
    query = urlencode(params) if params else ""
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
    return RedirectResponse(url=url, status_code=303)


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"on", "true", "1", "yes"}


def _as_int(value: str | None) -> int | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        return None
    return int(clean)


def _schedule_timezone_choices(rows: list[Schedule] | None = None) -> list[str]:
    choices = list(SCHEDULE_TIMEZONE_OPTIONS)
    seen = {v for v in choices}
    if rows:
        for row in rows:
            tz = (row.timezone or "").strip()
            if tz and tz not in seen:
                choices.append(tz)
                seen.add(tz)
    return choices


def _normalize_acl_customer_code(customer_code: str | None, is_master: str | None) -> str:
    if _as_bool(is_master):
        return MASTER_CUSTOMER_CODE
    clean = (customer_code or "").strip()
    if not clean:
        raise ValueError("Customer code obbligatorio se master user non e selezionato.")
    return clean


def _normalize_acl_filter_inputs(
    *,
    user_email: str,
    field_name: str,
    operator: str,
    field_value: str | None,
    is_master: str | None,
) -> tuple[str, str, str, str, bool]:
    email_clean = (user_email or "").strip().lower()
    if not email_clean:
        raise ValueError("Email utente obbligatoria.")

    master = _as_bool(is_master)
    if master:
        return email_clean, "__ALL__", "MASTER", "", True

    field_clean = (field_name or "").strip()
    if not field_clean:
        raise ValueError("Campo filtro obbligatorio se master non selezionato.")

    op_clean = (operator or "").strip().upper()
    if op_clean not in ACL_FILTER_OPERATOR_KEYS:
        raise ValueError("Operatore ACL non valido.")

    value_clean = (field_value or "").strip()
    if not value_clean:
        raise ValueError("Valore filtro obbligatorio se master non selezionato.")

    return email_clean, field_clean, op_clean, value_clean, False


def _bq_quote_identifier(value: str) -> str:
    clean = (value or "").strip().replace("`", "")
    return f"`{clean}`"


def _bq_quote_string(value: str) -> str:
    return "'" + (value or "").replace("'", "''") + "'"


def _split_csv_values(raw: str) -> list[str]:
    items = []
    for token in (raw or "").split(","):
        clean = token.strip()
        if clean:
            items.append(clean)
    return items


def _acl_predicate_for_field(field_name: str) -> str:
    col_ref = f"CAST(d.{_bq_quote_identifier(field_name)} AS STRING)"
    in_expr = (
        "STRPOS("
        "CONCAT(',', TRIM(REGEXP_REPLACE(COALESCE(a.field_value, ''), r'\\s*,\\s*', ',')), ','), "
        f"CONCAT(',', {col_ref}, ',')"
        ") > 0"
    )
    return (
        "("
        " (a.operator = 'EQ' AND {col} = a.field_value)"
        " OR (a.operator = 'NE' AND {col} <> a.field_value)"
        " OR (a.operator = 'CONTAINS' AND STRPOS(LOWER({col}), LOWER(COALESCE(a.field_value, ''))) > 0)"
        " OR (a.operator = 'STARTS_WITH' AND STARTS_WITH({col}, a.field_value))"
        " OR (a.operator = 'ENDS_WITH' AND ENDS_WITH({col}, a.field_value))"
        " OR (a.operator = 'IN' AND {in_expr})"
        " OR (a.operator = 'GT' AND SAFE_CAST({col} AS FLOAT64) > SAFE_CAST(a.field_value AS FLOAT64))"
        " OR (a.operator = 'GTE' AND SAFE_CAST({col} AS FLOAT64) >= SAFE_CAST(a.field_value AS FLOAT64))"
        " OR (a.operator = 'LT' AND SAFE_CAST({col} AS FLOAT64) < SAFE_CAST(a.field_value AS FLOAT64))"
        " OR (a.operator = 'LTE' AND SAFE_CAST({col} AS FLOAT64) <= SAFE_CAST(a.field_value AS FLOAT64))"
        ")"
    ).format(col=col_ref, in_expr=in_expr)


def _effective_bq_project_dataset(db: Session) -> tuple[str, str]:
    project_id = _load_setting(db, BQ_PROJECT_ID_SETTING_KEY, default=settings.bq_project_id).strip()
    dataset_raw = _load_setting(db, BQ_DATASET_SETTING_KEY, default=settings.bq_default_dataset).strip()
    dataset = dataset_raw
    if ":" in dataset_raw:
        p, d = dataset_raw.split(":", 1)
        if p.strip():
            project_id = p.strip()
        dataset = d.strip()
    elif dataset_raw.count(".") == 1:
        p, d = dataset_raw.split(".", 1)
        if p.strip():
            project_id = p.strip()
        dataset = d.strip()
    if not project_id:
        project_id = settings.bq_project_id
    return project_id, dataset


def _view_bq_target(db: Session, view_id: int) -> tuple[str | None, str | None]:
    row = (
        db.query(Pipeline)
        .filter(Pipeline.source_view_id == view_id)
        .order_by(Pipeline.id.desc())
        .first()
    )
    if not row:
        return None, None
    dataset = (row.bq_dataset or "").strip()
    table = (row.bq_table or "").strip()
    return dataset or None, table or None


def _build_looker_acl_query(
    *,
    db: Session,
    tenant_code: str,
    view_row: ReportView,
) -> str:
    project_id, default_dataset = _effective_bq_project_dataset(db)
    pipeline_dataset, pipeline_table = _view_bq_target(db, view_row.id)
    dataset = pipeline_dataset or default_dataset or "sap_reporting"
    table = pipeline_table or view_row.view_name

    acl_table = f"{project_id}.{dataset}.{BQ_ACL_FILTER_TABLE_DEFAULT}"
    data_table = f"{project_id}.{dataset}.{table}"
    view_name_literal = _bq_quote_string(view_row.view_name)
    tenant_literal = _bq_quote_string(tenant_code)

    field_names = (
        db.query(ACLFilterRule.field_name)
        .filter(ACLFilterRule.tenant_code == tenant_code)
        .filter(ACLFilterRule.view_id == view_row.id)
        .filter(ACLFilterRule.is_active.is_(True))
        .filter(ACLFilterRule.is_master.is_(False))
        .all()
    )
    normalized_fields = sorted({(row[0] or "").strip() for row in field_names if (row[0] or "").strip()})
    clauses = [f"(a.field_name = {_bq_quote_string(name)} AND {_acl_predicate_for_field(name)})" for name in normalized_fields]
    dynamic_where = " OR\n        ".join(clauses) if clauses else "FALSE"

    return (
        "WITH acl AS (\n"
        "  SELECT *\n"
        f"  FROM `{acl_table}`\n"
        "  WHERE is_active = TRUE\n"
        f"    AND tenant_code = {tenant_literal}\n"
        f"    AND view_name = {view_name_literal}\n"
        "    AND LOWER(user_email) = LOWER(@DS_USER_EMAIL)\n"
        ")\n"
        "SELECT\n"
        "  DISTINCT d.*\n"
        f"FROM `{data_table}` AS d\n"
        "JOIN acl AS a\n"
        "  ON (\n"
        "    a.is_master = TRUE\n"
        "    OR (\n"
        f"      {dynamic_where}\n"
        "    )\n"
        "  );"
    )


def _session_user_id(request: Request) -> int | None:
    session = request.scope.get("session")
    if not isinstance(session, dict):
        return None
    raw = session.get("user_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        session.clear()
        return None


def _get_current_user(request: Request, db: Session) -> AppUser | None:
    user_id = _session_user_id(request)
    if not user_id:
        return None
    try:
        row = db.get(AppUser, user_id)
    except Exception:  # noqa: BLE001
        db.rollback()
        session = request.scope.get("session")
        if isinstance(session, dict):
            session.clear()
        return None
    if not row or not row.is_active:
        session = request.scope.get("session")
        if isinstance(session, dict):
            session.clear()
        return None
    return row


def _is_admin(user: AppUser | None) -> bool:
    return bool(user and user.role == ROLE_ADMIN)


def _wizard_step_count(wizard: dict[str, object]) -> int:
    return len(_wizard_steps(wizard))


def _wizard_steps(wizard: dict[str, object]) -> list[dict[str, object]]:
    raw = wizard.get("steps")
    if not isinstance(raw, list):
        return []
    return [step for step in raw if isinstance(step, dict)]


def _wizard_step_id_by_index(wizard: dict[str, object], index: int) -> str:
    steps = _wizard_steps(wizard)
    if not steps:
        return ""
    safe_index = _clamp_step_index(index, len(steps))
    return str(steps[safe_index].get("id") or f"step_{safe_index}").strip()


def _wizard_step_index_by_id(wizard: dict[str, object], step_id: str | None) -> int:
    steps = _wizard_steps(wizard)
    if not steps:
        return 0
    clean = (step_id or "").strip()
    if not clean:
        return 0
    for idx, step in enumerate(steps):
        if str(step.get("id") or f"step_{idx}").strip() == clean:
            return idx
    return 0


def _clamp_step_index(index: int, steps_count: int) -> int:
    if steps_count <= 0:
        return 0
    return max(0, min(index, steps_count - 1))


def _wizard_session_store(request: Request) -> dict[str, object]:
    session = request.scope.get("session")
    if not isinstance(session, dict):
        return {}
    raw = session.get(WIZARD_DRAFTS_SESSION_KEY)
    if isinstance(raw, dict):
        return raw
    payload: dict[str, object] = {}
    session[WIZARD_DRAFTS_SESSION_KEY] = payload
    return payload


def _wizard_load_draft_entry(request: Request, wizard_id: str) -> dict[str, object]:
    store = _wizard_session_store(request)
    raw = store.get(wizard_id)
    if not isinstance(raw, dict):
        return {"data": {}, "updated_at": None}

    if "data" in raw and isinstance(raw.get("data"), dict):
        return {
            "data": dict(raw.get("data") or {}),
            "updated_at": raw.get("updated_at"),
            "step_index": raw.get("step_index"),
        }

    # backward compatibility: old payload contained only step data
    legacy_data = dict(raw)
    return {"data": legacy_data, "updated_at": None}


def _wizard_extract_step_payload(step: dict[str, object], form_data: dict[str, str]) -> dict[str, str]:
    step_type = str(step.get("type") or "").strip().lower()
    payload: dict[str, str] = {}

    fields = step.get("fields")
    if isinstance(fields, list):
        for field in fields:
            if not isinstance(field, dict):
                continue
            field_id = str(field.get("id") or "").strip()
            if not field_id:
                continue
            value = str(form_data.get(f"field__{field_id}", "")).strip()
            payload[field_id] = value

    if step_type == "choice":
        choice_value = str(form_data.get("choice_value", "")).strip()
        payload["value"] = choice_value

    return payload


def _wizard_render_context(
    *,
    wizard: dict[str, object],
    step_index: int,
    draft_data: dict[str, object],
) -> dict[str, object]:
    steps = _wizard_steps(wizard)
    steps_count = len(steps)
    safe_index = _clamp_step_index(step_index, steps_count)
    current_step = steps[safe_index] if steps_count else {}
    current_step_id = ""
    if isinstance(current_step, dict):
        current_step_id = str(current_step.get("id") or "")

    current_payload = draft_data.get(current_step_id)
    if not isinstance(current_payload, dict):
        current_payload = {}

    progress = int(((safe_index + 1) / steps_count) * 100) if steps_count else 0
    step_marker = f"Passo {safe_index + 1} di {steps_count}" if steps_count else "Passi non disponibili"
    return {
        "steps": steps,
        "steps_count": steps_count,
        "step_index": safe_index,
        "current_step": current_step,
        "current_step_id": current_step_id,
        "current_payload": current_payload,
        "progress": progress,
        "step_marker": step_marker,
        "has_previous": safe_index > 0,
        "has_next": safe_index < (steps_count - 1),
    }


def _wizard_status_from_draft_progress(progress: int) -> tuple[str, str, str]:
    if progress <= 0:
        return "not_configured", "Da configurare", "neutral"
    return "draft", "Bozza", "warning"


def _wizard_status_display(status: str | None, progress: int) -> tuple[str, str, str]:
    clean = (status or "").strip().lower()
    if clean == WIZARD_STATUS_COMPLETED:
        return "completed", "Completato", "success"
    if clean == WIZARD_STATUS_TEST_FAILED:
        return "test_failed", "Errore test", "danger"
    if clean == WIZARD_STATUS_WAITING_EXTERNAL_ACTION:
        return "waiting_external_action", "In attesa", "warning"
    if clean == WIZARD_STATUS_READY_TO_CONFIRM:
        return "ready_to_confirm", "Pronto conferma", "warning"
    if clean == WIZARD_STATUS_IN_PROGRESS:
        return "in_progress", "Bozza", "warning"
    if clean == WIZARD_STATUS_NOT_STARTED:
        return "not_configured", "Da configurare", "neutral"
    return _wizard_status_from_draft_progress(progress)


def _wizard_step_payload_map(draft_data: dict[str, object], step_id: str) -> dict[str, str]:
    raw = draft_data.get(step_id)
    if not isinstance(raw, dict):
        return {}
    payload: dict[str, str] = {}
    for key, value in raw.items():
        payload[str(key)] = str(value)
    return payload


def _apply_sap_wizard_to_settings(db: Session, session_row) -> str:
    draft_data = read_draft_data(session_row)
    engine_payload = _wizard_step_payload_map(draft_data, "engine")
    source_payload = _wizard_step_payload_map(draft_data, "server_and_db")
    credentials_payload = _wizard_step_payload_map(draft_data, "credentials")
    test_payload = _wizard_step_payload_map(draft_data, "test")

    db_engine = engine_payload.get("value", "").strip().lower()
    if db_engine not in {"sqlserver", "hana"}:
        raise ValueError("Seleziona il motore database (SQL Server o SAP HANA) nello step dedicato.")

    server = source_payload.get("server", "").strip()
    database = source_payload.get("database", "").strip()
    username = credentials_payload.get("uid", "").strip() or credentials_payload.get("username", "").strip()
    password = credentials_payload.get("pwd", "").strip() or credentials_payload.get("password", "").strip()
    test_result = test_payload.get("result", "").strip().lower()

    if test_result != "ok":
        raise ValueError("Step test non confermato: imposta esito test su OK prima della conferma finale.")

    if not server:
        raise ValueError("Server obbligatorio nello step 'Server e database'.")
    if not database:
        raise ValueError("Database obbligatorio nello step 'Server e database'.")
    if not username:
        raise ValueError("Username obbligatorio nello step 'Credenziali'.")
    if not password:
        raise ValueError("Password obbligatoria nello step 'Credenziali'.")

    if db_engine == "sqlserver":
        current_sql = _load_setting(db, SQLSERVER_CONN_STR_SETTING_KEY, default="")
        parsed_sql = _parse_sqlserver_conn_str(current_sql)
        conn_str = _build_sqlserver_conn_str(
            driver=str(parsed_sql.get("driver") or "ODBC Driver 17 for SQL Server"),
            server=server,
            instance=str(parsed_sql.get("instance") or ""),
            port=str(parsed_sql.get("port") or ""),
            database=database,
            uid=username,
            pwd=password,
            encrypt=bool(parsed_sql.get("encrypt")),
            trust_server_certificate=bool(parsed_sql.get("trust_server_certificate", True)),
        )
        server_name, db_name = test_sqlserver_connection(conn_str)
        _save_settings(
            db,
            {
                SOURCE_DB_ENGINE_SETTING_KEY: "sqlserver",
                SQLSERVER_CONN_STR_SETTING_KEY: conn_str,
            },
        )
        return (
            "Wizard SAP completato: impostazioni SQL Server salvate e testate "
            f"(Server={server_name} | Database={db_name})."
        )

    current_hana = _load_setting(db, HANA_CONN_STR_SETTING_KEY, default="")
    parsed_hana = _parse_hana_conn_str(current_hana)
    hana_server = server
    hana_port = str(parsed_hana.get("port") or "30015").strip() or "30015"
    if ":" in server:
        host, port = server.rsplit(":", 1)
        if host.strip() and port.strip():
            hana_server = host.strip()
            hana_port = port.strip()

    conn_str = _build_hana_conn_str(
        driver=str(parsed_hana.get("driver") or "HDBODBC"),
        server=hana_server,
        port=hana_port,
        database=database,
        uid=username,
        pwd=password,
        encrypt=bool(parsed_hana.get("encrypt")),
    )
    _save_settings(
        db,
        {
            SOURCE_DB_ENGINE_SETTING_KEY: "hana",
            HANA_CONN_STR_SETTING_KEY: conn_str,
        },
    )
    return (
        "Wizard SAP completato: impostazioni HANA salvate. "
        "Nota: test connessione HANA da verificare nell'ambiente operativo."
    )


def _fmt_last_updated(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%d/%m/%Y %H:%M")


def _build_wizard_cards(request: Request, db: Session) -> list[dict[str, str | int]]:
    cards: list[dict[str, str | int]] = []
    user_id = _session_user_id(request)
    tenant_id = "default"

    for raw in list_wizard_card_definitions():
        wizard_id = str(raw.get("id") or "").strip()
        wizard_def = get_wizard_definition(wizard_id) or {}
        steps = _wizard_steps(wizard_def)
        steps_count = len(steps)

        session_row = get_session(db, tenant_id, wizard_id, user_id=user_id)
        if session_row is None:
            draft_data = {}
            progress = 0
            status, status_label, status_class = ("not_configured", "Da configurare", "neutral")
            last_updated = None
        else:
            draft_data = read_draft_data(session_row)
            progress = calculate_progress(session_row, wizard_def)
            status, status_label, status_class = _wizard_status_display(session_row.status, progress)
            last_updated = session_row.updated_at
            if session_row.status == WIZARD_STATUS_COMPLETED:
                progress = 100

        completed_steps = 0
        for idx, step in enumerate(steps):
            step_id = str(step.get("id") or f"step_{idx}").strip()
            payload = draft_data.get(step_id)
            if isinstance(payload, dict) and any(str(v).strip() for v in payload.values()):
                completed_steps += 1

        if wizard_id == "full":
            summary = "Percorso guidato unico per configurare tutto da zero."
        elif status == "completed":
            summary = "Wizard completato."
        elif status == "test_failed":
            summary = "Ultimo test non superato. Apri il wizard e correggi i dati."
        elif status == "not_configured":
            summary = "Nessuna sessione avviata."
        else:
            summary = f"Bozza in corso: {completed_steps}/{steps_count} step compilati."

        last_updated_text = _fmt_last_updated(last_updated) or "n/d"

        action_label = "Avvia setup completo" if wizard_id == "full" else "Apri wizard"

        cards.append(
            {
                **raw,
                "progress": progress,
                "status": status,
                "status_label": status_label,
                "status_class": status_class,
                "summary": summary,
                "route": f"/ui/wizard/{wizard_id}",
                "action_label": action_label,
                "last_updated": last_updated_text,
                "has_last_updated": bool(last_updated),
                "steps_count": steps_count,
                "completed_steps": completed_steps,
                "wizard_session_status": session_row.status if session_row else WIZARD_STATUS_NOT_STARTED,
            }
        )
    return cards


def _wizard_definition_by_id(wizard_id: str) -> dict[str, object] | None:
    row = get_wizard_definition(wizard_id)
    if not row:
        return None
    return row


def _load_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppSetting, key)
    if not row:
        return default
    return row.value or default


def _save_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    db.commit()


def _save_settings(db: Session, values: dict[str, str]) -> None:
    for key, value in values.items():
        row = db.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=value)
            db.add(row)
        else:
            row.value = value
            row.updated_at = datetime.utcnow()
    db.commit()


def _escape_conn_value(value: str) -> str:
    clean = (value or "").strip()
    return clean.replace(";", r"\;")


def _parse_conn_kv(conn_str: str | None) -> dict[str, str]:
    payload: dict[str, str] = {}
    for token in (conn_str or "").split(";"):
        chunk = token.strip()
        if not chunk or "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        payload[key.strip().upper()] = value.strip()
    return payload


def _unbrace(value: str) -> str:
    clean = (value or "").strip()
    if clean.startswith("{") and clean.endswith("}"):
        return clean[1:-1].strip()
    return clean


def _to_bool_from_conn(value: str | None, default: bool = False) -> bool:
    clean = (value or "").strip().lower()
    if not clean:
        return default
    return clean in {"yes", "true", "1", "on"}


def _parse_sqlserver_conn_str(conn_str: str | None) -> dict[str, str | bool]:
    kv = _parse_conn_kv(conn_str)
    server_raw = kv.get("SERVER", "")
    server_host = server_raw
    server_instance = ""
    server_port = ""
    if "\\" in server_raw:
        server_host, server_instance = server_raw.split("\\", 1)
    elif "," in server_raw:
        server_host, server_port = server_raw.rsplit(",", 1)

    return {
        "driver": _unbrace(kv.get("DRIVER", "")),
        "server": server_host.strip(),
        "instance": server_instance.strip(),
        "port": server_port.strip(),
        "database": kv.get("DATABASE", "").strip(),
        "uid": kv.get("UID", "").strip(),
        "pwd": kv.get("PWD", "").strip(),
        "encrypt": _to_bool_from_conn(kv.get("ENCRYPT"), default=False),
        "trust_server_certificate": _to_bool_from_conn(kv.get("TRUSTSERVERCERTIFICATE"), default=True),
    }


def _parse_hana_conn_str(conn_str: str | None) -> dict[str, str | bool]:
    kv = _parse_conn_kv(conn_str)
    servernode = kv.get("SERVERNODE", "")
    hana_server = servernode
    hana_port = ""
    if ":" in servernode:
        hana_server, hana_port = servernode.rsplit(":", 1)
    return {
        "driver": _unbrace(kv.get("DRIVER", "")),
        "server": hana_server.strip(),
        "port": hana_port.strip(),
        "database": kv.get("DATABASENAME", "").strip(),
        "uid": kv.get("UID", "").strip(),
        "pwd": kv.get("PWD", "").strip(),
        "encrypt": _to_bool_from_conn(kv.get("ENCRYPT"), default=False),
    }


def _build_sqlserver_conn_str(
    *,
    driver: str,
    server: str,
    instance: str,
    port: str,
    database: str,
    uid: str,
    pwd: str,
    encrypt: bool,
    trust_server_certificate: bool,
) -> str:
    if not driver.strip():
        raise ValueError("Driver SQL Server obbligatorio.")
    if not server.strip():
        raise ValueError("Server SQL Server obbligatorio.")
    if not database.strip():
        raise ValueError("Database SQL Server obbligatorio.")
    if not uid.strip():
        raise ValueError("UID SQL Server obbligatorio.")
    if not pwd.strip():
        raise ValueError("Password SQL Server obbligatoria.")

    server_token = server.strip()
    if instance.strip():
        server_token = f"{server_token}\\{instance.strip()}"
    elif port.strip():
        server_token = f"{server_token},{port.strip()}"

    return (
        f"DRIVER={{{driver.strip()}}};"
        f"SERVER={_escape_conn_value(server_token)};"
        f"DATABASE={_escape_conn_value(database)};"
        f"UID={_escape_conn_value(uid)};"
        f"PWD={_escape_conn_value(pwd)};"
        f"Encrypt={'yes' if encrypt else 'no'};"
        f"TrustServerCertificate={'yes' if trust_server_certificate else 'no'};"
    )


def _build_hana_conn_str(
    *,
    driver: str,
    server: str,
    port: str,
    database: str,
    uid: str,
    pwd: str,
    encrypt: bool,
) -> str:
    if not driver.strip():
        raise ValueError("Driver HANA obbligatorio.")
    if not server.strip():
        raise ValueError("Server HANA obbligatorio.")
    if not port.strip():
        raise ValueError("Porta HANA obbligatoria.")
    if not uid.strip():
        raise ValueError("UID HANA obbligatorio.")
    if not pwd.strip():
        raise ValueError("Password HANA obbligatoria.")

    parts = [
        f"DRIVER={{{driver.strip()}}}",
        f"SERVERNODE={_escape_conn_value(server.strip())}:{_escape_conn_value(port.strip())}",
        f"UID={_escape_conn_value(uid)}",
        f"PWD={_escape_conn_value(pwd)}",
        f"ENCRYPT={'TRUE' if encrypt else 'FALSE'}",
    ]
    if database.strip():
        parts.append(f"DATABASENAME={_escape_conn_value(database)}")
    return ";".join(parts) + ";"


def _inspect_service_account_file(file_path: str) -> tuple[str | None, str | None]:
    raw_path = (file_path or "").strip()
    if not raw_path:
        return None, None
    path = Path(raw_path)
    if not path.exists():
        raise ValueError(f"File credenziali non trovato: {path}")
    if path.suffix.lower() != ".json":
        raise ValueError("File credenziali non valido: atteso un file .json")

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON credenziali non valido: {exc}") from exc

    client_email = (payload.get("client_email") or "").strip() or None
    project_id = (payload.get("project_id") or "").strip() or None
    return client_email, project_id


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    db: Session = Depends(get_db),
    next: str = Query(default="/"),  # noqa: A002
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    user = _get_current_user(request, db)
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "app_name": settings.app_name,
            "title": "Login",
            "active_nav": "",
            "next": next if next.startswith("/") else "/",
            "message": message,
            "error": error,
        },
    )


@router.post("/login")
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/"),  # noqa: A002
) -> RedirectResponse:
    if "session" not in request.scope:
        return _redirect("/login", error="Sessione non disponibile. Riavvia l'applicazione.")
    auth = authenticate_user(db, username=username, password=password)
    if not auth.ok or not auth.user:
        return _redirect("/login", error=auth.message)

    request.session["user_id"] = auth.user.id
    request.session["username"] = auth.user.username
    request.session["role"] = auth.user.role
    target = next if next.startswith("/") else "/"
    return RedirectResponse(url=target, status_code=303)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    session = request.scope.get("session")
    if isinstance(session, dict):
        session.clear()
    return _redirect("/login", message="Logout eseguito.")


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    return _render_overview(
        request=request,
        db=db,
        message=message,
        error=error,
        active_nav="overview",
    )


def _render_overview(
    *,
    request: Request,
    db: Session,
    message: str | None,
    error: str | None,
    active_nav: str,
) -> HTMLResponse:
    stats = {
        "views": db.query(func.count(ReportView.id)).scalar() or 0,
        "pipelines": db.query(func.count(Pipeline.id)).scalar() or 0,
        "schedules": db.query(func.count(Schedule.id)).scalar() or 0,
        "acl_rules": db.query(func.count(ACLRule.id)).scalar() or 0,
        "run_logs": db.query(func.count(RunLog.id)).scalar() or 0,
    }
    recent_runs = db.query(RunLog).order_by(RunLog.id.desc()).limit(15).all()
    pipelines = db.query(Pipeline).all()
    pipeline_by_id = {p.id: p for p in pipelines}

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "app_name": settings.app_name,
            "active_nav": active_nav,
            "stats": stats,
            "recent_runs": recent_runs,
            "pipeline_by_id": pipeline_by_id,
            "message": message,
            "error": error,
        },
    )


@router.get("/ui/overview", response_class=HTMLResponse)
def ui_overview(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    return _render_overview(
        request=request,
        db=db,
        message=message,
        error=error,
        active_nav="overview",
    )


@router.get("/ui/configurations", response_class=HTMLResponse)
def ui_configurations(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    cards = _build_wizard_cards(request, db)
    full_card = next((c for c in cards if str(c.get("id")) == "full"), None)
    wizard_cards = [c for c in cards if str(c.get("id")) != "full"]
    drafts_count = sum(
        1
        for c in wizard_cards
        if str(c.get("status")) in {"in_progress", "waiting_external_action", "ready_to_confirm", "test_failed"}
    )
    pending_count = sum(1 for c in wizard_cards if c["status"] == "not_configured")

    return templates.TemplateResponse(
        request=request,
        name="configurations.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "configurations",
            "full_card": full_card,
            "wizard_cards": wizard_cards,
            "drafts_count": drafts_count,
            "pending_count": pending_count,
            "total_count": len(wizard_cards),
            "message": message,
            "error": error,
        },
    )


@router.get("/ui/wizard/{wizard_id}", response_class=HTMLResponse)
def ui_wizard(
    wizard_id: str,
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
    step: int | None = Query(default=None),
) -> HTMLResponse:
    row = _wizard_definition_by_id(wizard_id)
    if row is None:
        return _redirect("/ui/configurations", error=f"Wizard '{wizard_id}' non riconosciuto.")

    steps_count = _wizard_step_count(row)
    if steps_count <= 0:
        return _redirect("/ui/configurations", error="Wizard non configurato.")

    user_id = _session_user_id(request)
    session_row = get_or_create_session(db, "default", wizard_id, user_id=user_id)

    # Temporary compatibility fallback: import old browser draft only once if DB draft is still empty.
    db_draft = read_draft_data(session_row)
    if not db_draft:
        legacy_entry = _wizard_load_draft_entry(request, wizard_id)
        legacy_data = legacy_entry.get("data")
        if isinstance(legacy_data, dict) and legacy_data:
            for step_key, payload in legacy_data.items():
                if not isinstance(payload, dict):
                    continue
                normalized_payload: dict[str, str] = {
                    str(k): str(v) for k, v in payload.items() if k is not None and v is not None
                }
                session_row = save_step_data(db, session_row, str(step_key), normalized_payload)
            raw_step_index = legacy_entry.get("step_index")
            if isinstance(raw_step_index, int):
                session_row = move_to_step(db, session_row, _wizard_step_id_by_index(row, raw_step_index))
        db_draft = read_draft_data(session_row)

    current_step_index = _wizard_step_index_by_id(row, session_row.current_step_id)
    resolved_step_id = _wizard_step_id_by_index(row, current_step_index)
    if session_row.current_step_id != resolved_step_id:
        session_row = move_to_step(db, session_row, resolved_step_id)

    if step is not None:
        forced_index = _clamp_step_index(step, steps_count)
        if forced_index != current_step_index:
            current_step_index = forced_index
            forced_step_id = _wizard_step_id_by_index(row, current_step_index)
            session_row = move_to_step(db, session_row, forced_step_id)

    cards = _build_wizard_cards(request, db)
    card = next((c for c in cards if str(c["id"]) == wizard_id), None)
    if card is None:
        return _redirect("/ui/configurations", error=f"Wizard '{wizard_id}' non disponibile.")

    draft_data = read_draft_data(session_row)
    wizard_ctx = _wizard_render_context(wizard=row, step_index=current_step_index, draft_data=draft_data)

    return templates.TemplateResponse(
        request=request,
        name="wizard.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "configurations",
            "wizard": card,
            "wizard_meta": row,
            "technical_route": card["technical_route"],
            "draft_data": draft_data,
            "wizard_session": session_row,
            **wizard_ctx,
            "message": message,
            "error": error,
        },
    )


@router.post("/ui/wizard/{wizard_id}")
async def ui_wizard_action(
    wizard_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    row = _wizard_definition_by_id(wizard_id)
    if row is None:
        return _redirect("/ui/configurations", error=f"Wizard '{wizard_id}' non riconosciuto.")

    form = await request.form()
    action = str(form.get("action", "continue")).strip().lower()
    try:
        step_index = int(str(form.get("step_index", "0")).strip() or "0")
    except ValueError:
        step_index = 0

    steps = _wizard_steps(row)
    steps_count = len(steps)
    if not steps:
        return _redirect("/ui/wizard/" + wizard_id, error="Wizard non configurato.")

    user_id = _session_user_id(request)
    session_row = get_or_create_session(db, "default", wizard_id, user_id=user_id)
    current_step_index = _wizard_step_index_by_id(row, session_row.current_step_id)
    current_step_id = _wizard_step_id_by_index(row, current_step_index)
    if session_row.current_step_id != current_step_id:
        session_row = move_to_step(db, session_row, current_step_id)

    # If form carries a different step index (e.g. stale tab), align session to requested step.
    aligned_step_index = _clamp_step_index(step_index, steps_count)
    if aligned_step_index != current_step_index:
        current_step_index = aligned_step_index
        current_step_id = _wizard_step_id_by_index(row, current_step_index)
        session_row = move_to_step(db, session_row, current_step_id)

    current_step = steps[current_step_index]

    form_data: dict[str, str] = {}
    for key, value in form.items():
        form_data[str(key)] = str(value)

    step_payload = _wizard_extract_step_payload(current_step, form_data)
    current_step_id = str(current_step.get("id") or f"step_{current_step_index}")
    session_row = save_step_data(db, session_row, current_step_id, step_payload)

    current_step_type = str(current_step.get("type") or "").strip().lower()
    if current_step_type == "test":
        result_values = []
        for key, value in step_payload.items():
            if key == "result" or key.endswith("_result"):
                result_values.append(str(value).strip().lower())
        if any(v in {"ko", "failed", "error"} for v in result_values):
            session_row = set_test_result(
                db,
                session_row,
                WIZARD_STATUS_TEST_FAILED,
                "Almeno un test e risultato KO.",
            )
        elif any(v in {"pending", ""} for v in result_values):
            session_row = set_test_result(
                db,
                session_row,
                WIZARD_STATUS_WAITING_EXTERNAL_ACTION,
                "Test non ancora completati.",
            )
        elif result_values:
            session_row = set_test_result(
                db,
                session_row,
                WIZARD_STATUS_IN_PROGRESS,
                "Test completati con esito positivo.",
            )

    if action == "back":
        move_back(db, session_row, row)
        return _redirect(f"/ui/wizard/{wizard_id}")

    if action == "save":
        return _redirect(
            f"/ui/wizard/{wizard_id}",
            message="Bozza wizard salvata.",
        )

    if current_step_index >= steps_count - 1:
        missing_required = required_step_missing_fields(session_row, row)
        if missing_required:
            preview = "; ".join(missing_required[:3])
            suffix = ""
            if len(missing_required) > 3:
                suffix = f" (+{len(missing_required) - 3} altri campi)"
            return _redirect(
                f"/ui/wizard/{wizard_id}",
                error=f"Compila i campi obbligatori prima della conferma finale: {preview}{suffix}",
            )
        completion_message = "Wizard completato."
        if wizard_id == "sap":
            try:
                completion_message = _apply_sap_wizard_to_settings(db, session_row)
            except (ValueError, SQLServerPublishError) as exc:
                set_test_result(
                    db,
                    session_row,
                    WIZARD_STATUS_TEST_FAILED,
                    str(exc),
                )
                return _redirect(
                    f"/ui/wizard/{wizard_id}",
                    error=f"Conferma finale non completata: {exc}",
                )
        mark_completed(db, session_row)
        return _redirect(
            f"/ui/wizard/{wizard_id}",
            message=completion_message,
        )

    move_next(db, session_row, row)
    return _redirect(f"/ui/wizard/{wizard_id}")


@router.get("/ui/summaries", response_class=HTMLResponse)
def ui_summaries(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    cards = _build_wizard_cards(request, db)
    return templates.TemplateResponse(
        request=request,
        name="summaries.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "summaries",
            "cards": cards,
            "message": message,
            "error": error,
        },
    )


@router.get("/ui/monitoring", response_class=HTMLResponse)
def ui_monitoring(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    return _render_overview(
        request=request,
        db=db,
        message=message,
        error=error,
        active_nav="monitoring",
    )


@router.get("/ui/users-access")
def ui_users_access(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    user = _get_current_user(request, db)
    if _is_admin(user):
        return RedirectResponse(url="/ui/users", status_code=303)
    return RedirectResponse(url="/ui/acl", status_code=303)


@router.get("/ui/advanced", response_class=HTMLResponse)
def ui_advanced(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    user = _get_current_user(request, db)
    return templates.TemplateResponse(
        request=request,
        name="advanced.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "advanced",
            "is_admin": _is_admin(user),
            "message": message,
            "error": error,
        },
    )


@router.get("/ui/views", response_class=HTMLResponse)
def ui_views(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    rows = db.query(ReportView).order_by(ReportView.id.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="views_list.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "views",
            "rows": rows,
            "message": message,
            "error": error,
        },
    )


@router.post("/ui/views/create")
def ui_views_create(
    db: Session = Depends(get_db),
    tenant_code: str = Form(default="default"),
    schema_name: str = Form(default="dbo"),
    view_name: str = Form(...),
    select_sql: str = Form(...),
    is_active: str | None = Form(default=None),
) -> RedirectResponse:
    row = ReportView(
        tenant_code=tenant_code.strip() or "default",
        schema_name=schema_name.strip() or "dbo",
        view_name=view_name.strip(),
        select_sql=select_sql.strip(),
        is_active=_as_bool(is_active),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        return _redirect("/ui/views", error=f"Errore creazione view: {exc}")
    return _redirect("/ui/views", message=f"View creata (ID {row.id}).")


@router.get("/ui/views/{view_id}", response_class=HTMLResponse)
def ui_view_detail(
    view_id: int,
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    row = db.get(ReportView, view_id)
    if not row:
        return templates.TemplateResponse(
            request=request,
            name="not_found.html",
            context={"app_name": settings.app_name, "active_nav": "views", "entity": "View"},
            status_code=404,
        )
    return templates.TemplateResponse(
        request=request,
        name="view_detail.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "views",
            "row": row,
            "message": message,
            "error": error,
        },
    )


@router.post("/ui/views/{view_id}/update")
def ui_view_update(
    view_id: int,
    db: Session = Depends(get_db),
    tenant_code: str = Form(default="default"),
    schema_name: str = Form(default="dbo"),
    view_name: str = Form(...),
    select_sql: str = Form(...),
    is_active: str | None = Form(default=None),
) -> RedirectResponse:
    row = db.get(ReportView, view_id)
    if not row:
        return _redirect("/ui/views", error="View non trovata.")

    new_sql = select_sql.strip()
    if new_sql != row.select_sql:
        row.version += 1

    row.tenant_code = tenant_code.strip() or "default"
    row.schema_name = schema_name.strip() or "dbo"
    row.view_name = view_name.strip()
    row.select_sql = new_sql
    row.is_active = _as_bool(is_active)
    row.updated_at = datetime.utcnow()

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        return _redirect(f"/ui/views/{view_id}", error=f"Errore aggiornamento view: {exc}")
    return _redirect(f"/ui/views/{view_id}", message="View aggiornata.")


@router.post("/ui/views/{view_id}/publish")
def ui_view_publish(view_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    row = db.get(ReportView, view_id)
    if not row:
        return _redirect("/ui/views", error="View non trovata.")
    try:
        publish_result = publish_view(row.schema_name, row.view_name, row.select_sql)
    except SQLServerPublishError as exc:
        return _redirect(f"/ui/views/{view_id}", error=f"Publish fallita: {exc}")
    row.last_published_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.commit()
    return _redirect(
        f"/ui/views/{view_id}",
        message=(
            "View pubblicata su SQL Server: "
            f"{publish_result.server_name} / {publish_result.db_name} / "
            f"{publish_result.schema_name}.{publish_result.view_name}"
        ),
    )


@router.post("/ui/views/{view_id}/delete")
def ui_view_delete(view_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    row = db.get(ReportView, view_id)
    if not row:
        return _redirect("/ui/views", error="View non trovata.")
    try:
        db.delete(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return _redirect("/ui/views", error=f"Impossibile eliminare view: {exc}")
    return _redirect("/ui/views", message="View eliminata.")


@router.get("/ui/pipelines", response_class=HTMLResponse)
def ui_pipelines(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    rows = db.query(Pipeline).order_by(Pipeline.id.desc()).all()
    views = db.query(ReportView).order_by(ReportView.id.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="pipelines_list.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "pipelines",
            "rows": rows,
            "views": views,
            "message": message,
            "error": error,
        },
    )


@router.post("/ui/pipelines/create")
def ui_pipelines_create(
    db: Session = Depends(get_db),
    tenant_code: str = Form(default="default"),
    name: str = Form(...),
    source_view_id: str | None = Form(default=None),
    bq_dataset: str = Form(default="sap_reporting"),
    bq_table: str = Form(default="stato_ordini_cliente"),
    write_mode: str = Form(default="WRITE_TRUNCATE"),
    command: str | None = Form(default=None),
    is_active: str | None = Form(default=None),
) -> RedirectResponse:
    try:
        source_view_id_int = _as_int(source_view_id)
    except ValueError:
        return _redirect("/ui/pipelines", error="source_view_id non valido.")
    if source_view_id_int is not None and not db.get(ReportView, source_view_id_int):
        return _redirect("/ui/pipelines", error="View sorgente non trovata.")

    row = Pipeline(
        tenant_code=tenant_code.strip() or "default",
        name=name.strip(),
        source_view_id=source_view_id_int,
        bq_dataset=bq_dataset.strip() or "sap_reporting",
        bq_table=bq_table.strip() or "stato_ordini_cliente",
        write_mode=write_mode.strip() or "WRITE_TRUNCATE",
        command=(command or "").strip() or None,
        is_active=_as_bool(is_active),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        return _redirect("/ui/pipelines", error=f"Errore creazione pipeline: {exc}")
    return _redirect("/ui/pipelines", message=f"Pipeline creata (ID {row.id}).")


@router.get("/ui/pipelines/{pipeline_id}", response_class=HTMLResponse)
def ui_pipeline_detail(
    pipeline_id: int,
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    row = db.get(Pipeline, pipeline_id)
    if not row:
        return templates.TemplateResponse(
            request=request,
            name="not_found.html",
            context={"app_name": settings.app_name, "active_nav": "pipelines", "entity": "Pipeline"},
            status_code=404,
        )
    views = db.query(ReportView).order_by(ReportView.id.desc()).all()
    runs = (
        db.query(RunLog)
        .filter(RunLog.pipeline_id == pipeline_id)
        .order_by(RunLog.id.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="pipeline_detail.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "pipelines",
            "row": row,
            "views": views,
            "runs": runs,
            "message": message,
            "error": error,
        },
    )


@router.post("/ui/pipelines/{pipeline_id}/update")
def ui_pipeline_update(
    pipeline_id: int,
    db: Session = Depends(get_db),
    tenant_code: str = Form(default="default"),
    name: str = Form(...),
    source_view_id: str | None = Form(default=None),
    bq_dataset: str = Form(default="sap_reporting"),
    bq_table: str = Form(default="stato_ordini_cliente"),
    write_mode: str = Form(default="WRITE_TRUNCATE"),
    command: str | None = Form(default=None),
    is_active: str | None = Form(default=None),
) -> RedirectResponse:
    row = db.get(Pipeline, pipeline_id)
    if not row:
        return _redirect("/ui/pipelines", error="Pipeline non trovata.")
    try:
        source_view_id_int = _as_int(source_view_id)
    except ValueError:
        return _redirect(f"/ui/pipelines/{pipeline_id}", error="source_view_id non valido.")
    if source_view_id_int is not None and not db.get(ReportView, source_view_id_int):
        return _redirect(f"/ui/pipelines/{pipeline_id}", error="View sorgente non trovata.")

    row.tenant_code = tenant_code.strip() or "default"
    row.name = name.strip()
    row.source_view_id = source_view_id_int
    row.bq_dataset = bq_dataset.strip() or "sap_reporting"
    row.bq_table = bq_table.strip() or "stato_ordini_cliente"
    row.write_mode = write_mode.strip() or "WRITE_TRUNCATE"
    row.command = (command or "").strip() or None
    row.is_active = _as_bool(is_active)
    row.updated_at = datetime.utcnow()

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        return _redirect(f"/ui/pipelines/{pipeline_id}", error=f"Errore aggiornamento pipeline: {exc}")
    return _redirect(f"/ui/pipelines/{pipeline_id}", message="Pipeline aggiornata.")


@router.post("/ui/pipelines/{pipeline_id}/run")
def ui_pipeline_run(pipeline_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    row = db.get(Pipeline, pipeline_id)
    if not row:
        return _redirect("/ui/pipelines", error="Pipeline non trovata.")
    run = run_pipeline(db, row)
    if run.status == "OK":
        return _redirect(f"/ui/pipelines/{pipeline_id}", message=f"Run completato (log {run.id}).")
    return _redirect(
        f"/ui/pipelines/{pipeline_id}",
        error=f"Run fallito (log {run.id}). Controlla il dettaglio nel riquadro run.",
    )


@router.post("/ui/pipelines/{pipeline_id}/delete")
def ui_pipeline_delete(pipeline_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    row = db.get(Pipeline, pipeline_id)
    if not row:
        return _redirect("/ui/pipelines", error="Pipeline non trovata.")
    try:
        db.delete(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return _redirect("/ui/pipelines", error=f"Impossibile eliminare pipeline: {exc}")
    reload_jobs()
    return _redirect("/ui/pipelines", message="Pipeline eliminata.")


@router.get("/ui/schedules", response_class=HTMLResponse)
def ui_schedules(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    rows = db.query(Schedule).order_by(Schedule.id.desc()).all()
    pipelines = db.query(Pipeline).order_by(Pipeline.id.desc()).all()
    pipeline_by_id = {p.id: p for p in pipelines}
    timezone_options = _schedule_timezone_choices(rows)
    return templates.TemplateResponse(
        request=request,
        name="schedules.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "schedules",
            "rows": rows,
            "pipelines": pipelines,
            "pipeline_by_id": pipeline_by_id,
            "timezone_options": timezone_options,
            "message": message,
            "error": error,
        },
    )


@router.post("/ui/schedules/create")
def ui_schedules_create(
    db: Session = Depends(get_db),
    pipeline_id: str = Form(...),
    cron_expression: str = Form(...),
    timezone: str = Form(default="Europe/Rome"),
    is_active: str | None = Form(default=None),
) -> RedirectResponse:
    try:
        pipeline_id_int = _as_int(pipeline_id)
    except ValueError:
        return _redirect("/ui/schedules", error="pipeline_id non valido.")
    if pipeline_id_int is None:
        return _redirect("/ui/schedules", error="pipeline_id obbligatorio.")

    pipeline = db.get(Pipeline, pipeline_id_int)
    if not pipeline:
        return _redirect("/ui/schedules", error="Pipeline non trovata.")

    timezone_clean = timezone.strip() or "Europe/Rome"

    try:
        validate_cron_expression(cron_expression.strip(), timezone_clean)
    except ValueError as exc:
        return _redirect("/ui/schedules", error=f"Cron non valido: {exc}")

    row = Schedule(
        pipeline_id=pipeline_id_int,
        cron_expression=cron_expression.strip(),
        timezone=timezone_clean,
        is_active=_as_bool(is_active),
    )
    db.add(row)
    db.commit()
    reload_jobs()
    return _redirect("/ui/schedules", message=f"Schedule creata (ID {row.id}).")


@router.post("/ui/schedules/{schedule_id}/update")
def ui_schedule_update(
    schedule_id: int,
    db: Session = Depends(get_db),
    cron_expression: str = Form(...),
    timezone: str = Form(default="Europe/Rome"),
    is_active: str | None = Form(default=None),
) -> RedirectResponse:
    row = db.get(Schedule, schedule_id)
    if not row:
        return _redirect("/ui/schedules", error="Schedule non trovata.")

    timezone_clean = timezone.strip() or "Europe/Rome"

    try:
        validate_cron_expression(cron_expression.strip(), timezone_clean)
    except ValueError as exc:
        return _redirect("/ui/schedules", error=f"Cron non valido: {exc}")

    row.cron_expression = cron_expression.strip()
    row.timezone = timezone_clean
    row.is_active = _as_bool(is_active)
    row.updated_at = datetime.utcnow()
    db.commit()
    reload_jobs()
    return _redirect("/ui/schedules", message=f"Schedule {schedule_id} aggiornata.")


@router.post("/ui/schedules/{schedule_id}/delete")
def ui_schedule_delete(schedule_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    row = db.get(Schedule, schedule_id)
    if not row:
        return _redirect("/ui/schedules", error="Schedule non trovata.")
    db.delete(row)
    db.commit()
    reload_jobs()
    return _redirect("/ui/schedules", message=f"Schedule {schedule_id} eliminata.")


def _acl_path(tenant_code: str, acl_view_id: str | None = None) -> str:
    tenant = (tenant_code or "").strip() or "default"
    if acl_view_id and acl_view_id.strip():
        return f"/ui/acl?tenant_code={tenant}&acl_view_id={acl_view_id.strip()}"
    return f"/ui/acl?tenant_code={tenant}"


@router.get("/ui/acl", response_class=HTMLResponse)
def ui_acl(
    request: Request,
    db: Session = Depends(get_db),
    tenant_code: str = Query(default="default"),
    acl_view_id: str | None = Query(default=None),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    rules = (
        db.query(ACLRule)
        .filter(ACLRule.tenant_code == tenant_code)
        .order_by(ACLRule.user_email.asc(), ACLRule.customer_code.asc())
        .all()
    )
    views = db.query(ReportView).order_by(ReportView.view_name.asc()).all()

    selected_view_id: int | None = None
    try:
        selected_view_id = _as_int(acl_view_id)
    except (TypeError, ValueError):
        selected_view_id = None
    if selected_view_id is None and views:
        selected_view_id = views[0].id

    filter_rules_query = (
        db.query(ACLFilterRule, ReportView)
        .join(ReportView, ReportView.id == ACLFilterRule.view_id)
        .filter(ACLFilterRule.tenant_code == tenant_code)
        .order_by(ReportView.view_name.asc(), ACLFilterRule.user_email.asc(), ACLFilterRule.id.desc())
    )
    filter_rules = filter_rules_query.all()

    looker_query_sql = ""
    selected_view_row = None
    if selected_view_id is not None:
        selected_view_row = db.get(ReportView, selected_view_id)
        if selected_view_row:
            looker_query_sql = _build_looker_acl_query(
                db=db,
                tenant_code=tenant_code,
                view_row=selected_view_row,
            )

    return templates.TemplateResponse(
        request=request,
        name="acl.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "acl",
            "tenant_code": tenant_code,
            "rules": rules,
            "master_customer_code": MASTER_CUSTOMER_CODE,
            "filter_rules": filter_rules,
            "views": views,
            "selected_view_id": selected_view_id,
            "selected_view_row": selected_view_row,
            "acl_filter_operators": ACL_FILTER_OPERATORS,
            "looker_query_sql": looker_query_sql,
            "message": message,
            "error": error,
        },
    )


@router.post("/ui/acl/create")
def ui_acl_create(
    db: Session = Depends(get_db),
    tenant_code: str = Form(default="default"),
    acl_view_id: str | None = Form(default=None),
    user_email: str = Form(...),
    customer_code: str = Form(default=""),
    is_master: str | None = Form(default=None),
    is_active: str | None = Form(default=None),
    note: str | None = Form(default=None),
) -> RedirectResponse:
    try:
        customer_code_clean = _normalize_acl_customer_code(customer_code, is_master)
    except ValueError as exc:
        return _redirect(_acl_path(tenant_code, acl_view_id), error=str(exc))

    row = ACLRule(
        tenant_code=tenant_code.strip() or "default",
        user_email=user_email.lower().strip(),
        customer_code=customer_code_clean,
        is_active=_as_bool(is_active),
        note=(note or "").strip() or None,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        return _redirect(_acl_path(tenant_code, acl_view_id), error=f"Errore creazione ACL: {exc}")
    try:
        sync_msg = sync_acl_rules_to_bigquery(db)
        return _redirect(
            _acl_path(tenant_code, acl_view_id),
            message=f"Regola ACL creata (ID {row.id}). {sync_msg}",
        )
    except BigQueryServiceError as exc:
        return _redirect(
            _acl_path(tenant_code, acl_view_id),
            message=f"Regola ACL creata (ID {row.id}).",
            error=f"ATTENZIONE: sync ACL su BigQuery non riuscita: {exc}",
        )


@router.post("/ui/acl/{rule_id}/update")
def ui_acl_update(
    rule_id: int,
    db: Session = Depends(get_db),
    tenant_code: str = Form(default="default"),
    acl_view_id: str | None = Form(default=None),
    user_email: str = Form(...),
    customer_code: str = Form(default=""),
    is_master: str | None = Form(default=None),
    is_active: str | None = Form(default=None),
    note: str | None = Form(default=None),
) -> RedirectResponse:
    row = db.get(ACLRule, rule_id)
    if not row:
        return _redirect(_acl_path(tenant_code, acl_view_id), error="Regola ACL non trovata.")

    try:
        customer_code_clean = _normalize_acl_customer_code(customer_code, is_master)
    except ValueError as exc:
        return _redirect(_acl_path(tenant_code, acl_view_id), error=str(exc))

    row.tenant_code = tenant_code.strip() or "default"
    row.user_email = user_email.lower().strip()
    row.customer_code = customer_code_clean
    row.is_active = _as_bool(is_active)
    row.note = (note or "").strip() or None
    row.updated_at = datetime.utcnow()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        return _redirect(_acl_path(tenant_code, acl_view_id), error=f"Errore aggiornamento ACL: {exc}")
    try:
        sync_msg = sync_acl_rules_to_bigquery(db)
        return _redirect(
            _acl_path(tenant_code, acl_view_id),
            message=f"Regola ACL {rule_id} aggiornata. {sync_msg}",
        )
    except BigQueryServiceError as exc:
        return _redirect(
            _acl_path(tenant_code, acl_view_id),
            message=f"Regola ACL {rule_id} aggiornata.",
            error=f"ATTENZIONE: sync ACL su BigQuery non riuscita: {exc}",
        )


@router.post("/ui/acl/{rule_id}/delete")
def ui_acl_delete(
    rule_id: int,
    db: Session = Depends(get_db),
    tenant_code: str = Form(default="default"),
    acl_view_id: str | None = Form(default=None),
) -> RedirectResponse:
    row = db.get(ACLRule, rule_id)
    if not row:
        return _redirect(_acl_path(tenant_code, acl_view_id), error="Regola ACL non trovata.")
    db.delete(row)
    db.commit()
    try:
        sync_msg = sync_acl_rules_to_bigquery(db)
        return _redirect(
            _acl_path(tenant_code, acl_view_id),
            message=f"Regola ACL {rule_id} eliminata. {sync_msg}",
        )
    except BigQueryServiceError as exc:
        return _redirect(
            _acl_path(tenant_code, acl_view_id),
            message=f"Regola ACL {rule_id} eliminata.",
            error=f"ATTENZIONE: sync ACL su BigQuery non riuscita: {exc}",
        )


@router.post("/ui/acl/sync")
def ui_acl_sync(
    db: Session = Depends(get_db),
    tenant_code: str = Form(default="default"),
    acl_view_id: str | None = Form(default=None),
) -> RedirectResponse:
    messages = []
    try:
        messages.append(sync_acl_rules_to_bigquery(db))
        messages.append(sync_acl_filter_rules_to_bigquery(db))
        return _redirect(_acl_path(tenant_code, acl_view_id), message=" | ".join(messages))
    except BigQueryServiceError as exc:
        return _redirect(_acl_path(tenant_code, acl_view_id), error=f"Sync ACL BigQuery fallita: {exc}")


@router.post("/ui/acl/filters/create")
def ui_acl_filter_create(
    db: Session = Depends(get_db),
    tenant_code: str = Form(default="default"),
    view_id: str = Form(...),
    user_email: str = Form(...),
    field_name: str = Form(default=""),
    operator: str = Form(default="EQ"),
    field_value: str = Form(default=""),
    is_master: str | None = Form(default=None),
    is_active: str | None = Form(default=None),
    note: str | None = Form(default=None),
) -> RedirectResponse:
    try:
        view_id_int = _as_int(view_id)
    except (TypeError, ValueError):
        return _redirect(_acl_path(tenant_code, None), error="View ACL non valida.")
    if view_id_int is None:
        return _redirect(_acl_path(tenant_code, None), error="View ACL obbligatoria.")
    if not db.get(ReportView, view_id_int):
        return _redirect(_acl_path(tenant_code, None), error="View ACL non trovata.")

    try:
        email_clean, field_clean, op_clean, value_clean, is_master_bool = _normalize_acl_filter_inputs(
            user_email=user_email,
            field_name=field_name,
            operator=operator,
            field_value=field_value,
            is_master=is_master,
        )
    except ValueError as exc:
        return _redirect(_acl_path(tenant_code, str(view_id_int)), error=str(exc))

    row = ACLFilterRule(
        tenant_code=tenant_code.strip() or "default",
        view_id=view_id_int,
        user_email=email_clean,
        field_name=field_clean,
        operator=op_clean,
        field_value=value_clean,
        is_master=is_master_bool,
        is_active=_as_bool(is_active),
        note=(note or "").strip() or None,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        return _redirect(_acl_path(tenant_code, str(view_id_int)), error=f"Errore creazione ACL filtro: {exc}")
    try:
        sync_msg = sync_acl_filter_rules_to_bigquery(db)
        return _redirect(
            _acl_path(tenant_code, str(view_id_int)),
            message=f"ACL filtro creata (ID {row.id}). {sync_msg}",
        )
    except BigQueryServiceError as exc:
        return _redirect(
            _acl_path(tenant_code, str(view_id_int)),
            message=f"ACL filtro creata (ID {row.id}).",
            error=f"ATTENZIONE: sync ACL filtri su BigQuery non riuscita: {exc}",
        )


@router.post("/ui/acl/filters/{filter_id}/delete")
def ui_acl_filter_delete(
    filter_id: int,
    db: Session = Depends(get_db),
    tenant_code: str = Form(default="default"),
    acl_view_id: str | None = Form(default=None),
) -> RedirectResponse:
    row = db.get(ACLFilterRule, filter_id)
    if not row:
        return _redirect(_acl_path(tenant_code, acl_view_id), error="ACL filtro non trovata.")
    db.delete(row)
    db.commit()
    try:
        sync_msg = sync_acl_filter_rules_to_bigquery(db)
        return _redirect(
            _acl_path(tenant_code, acl_view_id),
            message=f"ACL filtro {filter_id} eliminata. {sync_msg}",
        )
    except BigQueryServiceError as exc:
        return _redirect(
            _acl_path(tenant_code, acl_view_id),
            message=f"ACL filtro {filter_id} eliminata.",
            error=f"ATTENZIONE: sync ACL filtri su BigQuery non riuscita: {exc}",
        )


@router.get("/ui/settings", response_class=HTMLResponse)
def ui_settings(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
    message_scope: str | None = Query(default=None),
    error_scope: str | None = Query(default=None),
) -> HTMLResponse:
    source_db_engine = _load_setting(db, SOURCE_DB_ENGINE_SETTING_KEY, default="sqlserver").strip().lower() or "sqlserver"
    sqlserver_conn_str = _load_setting(db, SQLSERVER_CONN_STR_SETTING_KEY, default="")
    hana_conn_str = _load_setting(db, HANA_CONN_STR_SETTING_KEY, default="")
    env_conn_str = settings.sqlserver_conn_str
    bq_project_id = _load_setting(db, BQ_PROJECT_ID_SETTING_KEY, default="")
    bq_dataset = _load_setting(db, BQ_DATASET_SETTING_KEY, default="")
    bq_table = _load_setting(db, BQ_TABLE_SETTING_KEY, default="")
    bq_location = _load_setting(db, BQ_LOCATION_SETTING_KEY, default="")
    bq_credentials_file = _load_setting(db, BQ_CREDENTIALS_FILE_SETTING_KEY, default="")

    effective_sql_conn_str = sqlserver_conn_str.strip() or (env_conn_str or "").strip()
    parsed_sql = _parse_sqlserver_conn_str(effective_sql_conn_str)
    parsed_hana = _parse_hana_conn_str(hana_conn_str)

    active_conn_label = "SQL Server (non configurata)"
    active_conn_value = effective_sql_conn_str
    if source_db_engine == "hana":
        if hana_conn_str.strip():
            active_conn_label = "SAP HANA (impostazioni app)"
            active_conn_value = hana_conn_str.strip()
        else:
            active_conn_label = "SAP HANA (non configurata)"
            active_conn_value = ""
    else:
        if sqlserver_conn_str.strip():
            active_conn_label = "SQL Server (impostazioni app)"
        elif effective_sql_conn_str:
            active_conn_label = "SQL Server (fallback .env)"

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "settings",
            "suppress_global_flash": True,
            "source_db_engine": source_db_engine,
            "sqlserver_conn_str": sqlserver_conn_str,
            "hana_conn_str": hana_conn_str,
            "env_conn_str": env_conn_str,
            "active_conn_label": active_conn_label,
            "active_conn_value": active_conn_value,
            "bq_project_id": bq_project_id,
            "bq_dataset": bq_dataset,
            "bq_table": bq_table,
            "bq_location": bq_location,
            "bq_credentials_file": bq_credentials_file,
            "env_bq_project_id": settings.bq_project_id,
            "env_bq_dataset": settings.bq_default_dataset,
            "env_bq_table": settings.bq_default_table,
            "env_bq_location": settings.bq_location,
            "env_bq_credentials_file": settings.bq_credentials_file,
            "wizard_sql_driver": str(parsed_sql.get("driver") or "ODBC Driver 17 for SQL Server"),
            "wizard_sql_server": str(parsed_sql.get("server") or ""),
            "wizard_sql_instance": str(parsed_sql.get("instance") or ""),
            "wizard_sql_port": str(parsed_sql.get("port") or ""),
            "wizard_sql_database": str(parsed_sql.get("database") or ""),
            "wizard_sql_uid": str(parsed_sql.get("uid") or ""),
            "wizard_sql_pwd": str(parsed_sql.get("pwd") or ""),
            "wizard_sql_encrypt": bool(parsed_sql.get("encrypt")),
            "wizard_sql_trust_server_certificate": bool(parsed_sql.get("trust_server_certificate")),
            "wizard_hana_driver": str(parsed_hana.get("driver") or "HDBODBC"),
            "wizard_hana_server": str(parsed_hana.get("server") or ""),
            "wizard_hana_port": str(parsed_hana.get("port") or "30015"),
            "wizard_hana_database": str(parsed_hana.get("database") or ""),
            "wizard_hana_uid": str(parsed_hana.get("uid") or ""),
            "wizard_hana_pwd": str(parsed_hana.get("pwd") or ""),
            "wizard_hana_encrypt": bool(parsed_hana.get("encrypt")),
            "message": message,
            "error": error,
            "message_scope": message_scope or "",
            "error_scope": error_scope or "",
        },
    )


@router.post("/ui/settings/sqlserver/save")
def ui_settings_sqlserver_save(
    db: Session = Depends(get_db),
    sqlserver_conn_str: str = Form(default=""),
) -> RedirectResponse:
    value = sqlserver_conn_str.strip()
    if not value:
        _save_setting(db, SQLSERVER_CONN_STR_SETTING_KEY, "")
        return _redirect(
            "/ui/settings",
            message="Stringa SQL Server rimossa: verra usato SQLSERVER_CONN_STR dal file .env se presente.",
            message_scope="db",
        )
    try:
        server_name, db_name = test_sqlserver_connection(value)
    except SQLServerPublishError as exc:
        return _redirect(
            "/ui/settings",
            error=f"Salvataggio annullato: test connessione fallito ({exc}).",
            error_scope="db",
        )
    _save_setting(db, SQLSERVER_CONN_STR_SETTING_KEY, value)
    return _redirect(
        "/ui/settings",
        message=f"Connessione SQL Server salvata e testata: Server={server_name} | Database={db_name}",
        message_scope="db",
    )


@router.post("/ui/settings/sqlserver/test")
def ui_settings_sqlserver_test(
    db: Session = Depends(get_db),
    sqlserver_conn_str: str = Form(default=""),
) -> RedirectResponse:
    value = sqlserver_conn_str.strip() or _load_setting(db, SQLSERVER_CONN_STR_SETTING_KEY, default="").strip()
    try:
        server_name, db_name = test_sqlserver_connection(value)
    except SQLServerPublishError as exc:
        return _redirect("/ui/settings", error=f"Test connessione fallito: {exc}", error_scope="db")
    return _redirect(
        "/ui/settings",
        message=f"Connessione OK. Server={server_name} | Database={db_name}",
        message_scope="db",
    )


@router.post("/ui/settings/db/wizard/apply")
def ui_settings_db_wizard_apply(
    db: Session = Depends(get_db),
    db_engine: str = Form(default="sqlserver"),
    sql_driver: str = Form(default="ODBC Driver 17 for SQL Server"),
    sql_server: str = Form(default=""),
    sql_instance: str = Form(default=""),
    sql_port: str = Form(default=""),
    sql_database: str = Form(default=""),
    sql_uid: str = Form(default=""),
    sql_pwd: str = Form(default=""),
    sql_encrypt: str | None = Form(default=None),
    sql_trust_server_certificate: str | None = Form(default=None),
    hana_driver: str = Form(default="HDBODBC"),
    hana_server: str = Form(default=""),
    hana_port: str = Form(default="30015"),
    hana_database: str = Form(default=""),
    hana_uid: str = Form(default=""),
    hana_pwd: str = Form(default=""),
    hana_encrypt: str | None = Form(default=None),
) -> RedirectResponse:
    engine = (db_engine or "").strip().lower()
    if engine not in {"sqlserver", "hana"}:
        return _redirect(
            "/ui/settings",
            error="Database engine non supportato. Usa sqlserver o hana.",
            error_scope="db",
        )

    try:
        if engine == "sqlserver":
            conn_str = _build_sqlserver_conn_str(
                driver=sql_driver,
                server=sql_server,
                instance=sql_instance,
                port=sql_port,
                database=sql_database,
                uid=sql_uid,
                pwd=sql_pwd,
                encrypt=_as_bool(sql_encrypt),
                trust_server_certificate=_as_bool(sql_trust_server_certificate),
            )
            server_name, db_name = test_sqlserver_connection(conn_str)
            _save_settings(
                db,
                {
                    SOURCE_DB_ENGINE_SETTING_KEY: "sqlserver",
                    SQLSERVER_CONN_STR_SETTING_KEY: conn_str,
                },
            )
            return _redirect(
                "/ui/settings",
                message=(
                    "Wizard SQL Server completato: stringa applicata e testata "
                    f"(Server={server_name} | Database={db_name})."
                ),
                message_scope="db",
            )

        conn_str = _build_hana_conn_str(
            driver=hana_driver,
            server=hana_server,
            port=hana_port,
            database=hana_database,
            uid=hana_uid,
            pwd=hana_pwd,
            encrypt=_as_bool(hana_encrypt),
        )
        _save_settings(
            db,
            {
                SOURCE_DB_ENGINE_SETTING_KEY: "hana",
                HANA_CONN_STR_SETTING_KEY: conn_str,
            },
        )
        return _redirect(
            "/ui/settings",
            message=(
                "Wizard HANA completato: stringa salvata. "
                "Nota: publish view e managed pipeline al momento sono ottimizzati per SQL Server."
            ),
            message_scope="db",
        )
    except SQLServerPublishError as exc:
        return _redirect(
            "/ui/settings",
            error=f"Wizard SQL Server: test connessione fallito ({exc}).",
            error_scope="db",
        )
    except ValueError as exc:
        return _redirect("/ui/settings", error=f"Wizard non valido: {exc}", error_scope="db")


@router.post("/ui/settings/bigquery/save")
def ui_settings_bigquery_save(
    db: Session = Depends(get_db),
    bq_project_id: str = Form(default=""),
    bq_dataset: str = Form(default=""),
    bq_table: str = Form(default=""),
    bq_location: str = Form(default=""),
    bq_credentials_file: str = Form(default=""),
) -> RedirectResponse:
    values = {
        BQ_PROJECT_ID_SETTING_KEY: bq_project_id.strip(),
        BQ_DATASET_SETTING_KEY: bq_dataset.strip(),
        BQ_TABLE_SETTING_KEY: bq_table.strip(),
        BQ_LOCATION_SETTING_KEY: bq_location.strip(),
        BQ_CREDENTIALS_FILE_SETTING_KEY: bq_credentials_file.strip(),
    }
    _save_settings(db, values)
    return _redirect("/ui/settings", message="Impostazioni BigQuery salvate.", message_scope="bq_save")


@router.post("/ui/settings/bigquery/test")
def ui_settings_bigquery_test(
    db: Session = Depends(get_db),
    bq_project_id: str = Form(default=""),
    bq_dataset: str = Form(default=""),
    bq_location: str = Form(default=""),
    bq_credentials_file: str = Form(default=""),
) -> RedirectResponse:
    try:
        project, detail = test_bigquery_connection(
            db,
            project_id=bq_project_id.strip() or None,
            dataset=bq_dataset.strip() or None,
            location=bq_location.strip() or None,
            credentials_file=bq_credentials_file.strip() or None,
        )
    except BigQueryServiceError as exc:
        return _redirect("/ui/settings", error=f"Test BigQuery fallito: {exc}", error_scope="bq_test")
    return _redirect(
        "/ui/settings",
        message=f"BigQuery OK. Project={project} | {detail}",
        message_scope="bq_test",
    )


@router.post("/ui/settings/bigquery/bootstrap")
def ui_settings_bigquery_bootstrap(
    db: Session = Depends(get_db),
    bq_project_id: str = Form(default=""),
    bq_dataset: str = Form(default=""),
    bq_location: str = Form(default=""),
    bq_credentials_file: str = Form(default=""),
) -> RedirectResponse:
    try:
        dataset_id = ensure_dataset(
            db,
            project_id=bq_project_id.strip() or None,
            dataset=bq_dataset.strip() or None,
            location=bq_location.strip() or None,
            credentials_file=bq_credentials_file.strip() or None,
        )
    except BigQueryServiceError as exc:
        return _redirect(
            "/ui/settings",
            error=f"Bootstrap BigQuery fallito: {exc}",
            error_scope="bq_bootstrap",
        )
    return _redirect(
        "/ui/settings",
        message=f"Dataset pronto: {dataset_id}",
        message_scope="bq_bootstrap",
    )


@router.post("/ui/settings/bigquery/setup-assistant")
def ui_settings_bigquery_setup_assistant(
    db: Session = Depends(get_db),
    bq_project_id: str = Form(default=""),
    bq_dataset: str = Form(default=""),
    bq_table: str = Form(default=""),
    bq_location: str = Form(default=""),
    bq_credentials_file: str = Form(default=""),
) -> RedirectResponse:
    project_id = bq_project_id.strip()
    dataset = bq_dataset.strip()
    table = bq_table.strip()
    location = bq_location.strip() or "EU"
    credentials_file = bq_credentials_file.strip()

    if not project_id:
        return _redirect(
            "/ui/settings",
            error="Setup BigQuery: Project ID obbligatorio.",
            error_scope="bq_setup",
        )
    if not dataset:
        return _redirect(
            "/ui/settings",
            error="Setup BigQuery: Dataset obbligatorio.",
            error_scope="bq_setup",
        )

    try:
        sa_email, sa_project = _inspect_service_account_file(credentials_file)
    except ValueError as exc:
        return _redirect("/ui/settings", error=f"Setup BigQuery: {exc}", error_scope="bq_setup")

    _save_settings(
        db,
        {
            BQ_PROJECT_ID_SETTING_KEY: project_id,
            BQ_DATASET_SETTING_KEY: dataset,
            BQ_TABLE_SETTING_KEY: table,
            BQ_LOCATION_SETTING_KEY: location,
            BQ_CREDENTIALS_FILE_SETTING_KEY: credentials_file,
        },
    )

    try:
        test_project, test_detail = test_bigquery_connection(
            db,
            project_id=project_id,
            dataset=dataset,
            location=location,
            credentials_file=credentials_file or None,
        )
        dataset_id = ensure_dataset(
            db,
            project_id=project_id,
            dataset=dataset,
            location=location,
            credentials_file=credentials_file or None,
        )
    except BigQueryServiceError as exc:
        return _redirect(
            "/ui/settings",
            error=f"Setup BigQuery fallito dopo salvataggio impostazioni: {exc}",
            error_scope="bq_setup",
        )

    notes: list[str] = [
        "Setup BigQuery completato.",
        f"Project effettivo={test_project}.",
        test_detail,
        f"Dataset pronto: {dataset_id}.",
    ]
    if sa_email:
        notes.append(f"Service account: {sa_email}.")
    if sa_project and sa_project != project_id:
        notes.append(
            f"Attenzione: il JSON credenziali usa project {sa_project} (diverso da {project_id})."
        )
    return _redirect("/ui/settings", message=" ".join(notes), message_scope="bq_setup")


@router.get("/ui/users", response_class=HTMLResponse)
def ui_users(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    rows: list[AppUser] = []
    users_error = error
    try:
        rows = db.query(AppUser).order_by(AppUser.username.asc()).all()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        users_error = f"Errore caricamento utenti: {exc}"
    current_user = _get_current_user(request, db)
    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "users",
            "rows": rows,
            "current_user_id": current_user.id if current_user else None,
            "roles": [ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER],
            "message": message,
            "error": users_error,
        },
    )


@router.post("/ui/users/create")
def ui_users_create(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(default=ROLE_VIEWER),
    is_active: str | None = Form(default=None),
) -> RedirectResponse:
    username_clean = username.strip().lower()
    if not username_clean:
        return _redirect("/ui/users", error="Username obbligatorio.")
    if db.query(AppUser).filter(AppUser.username == username_clean).first():
        return _redirect("/ui/users", error="Username gia esistente.")
    if len(password) < 8:
        return _redirect("/ui/users", error="Password troppo corta (minimo 8 caratteri).")

    row = AppUser(
        username=username_clean,
        password_hash=hash_password(password),
        role=normalize_role(role),
        is_active=_as_bool(is_active),
    )
    db.add(row)
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return _redirect("/ui/users", error=f"Errore creazione utente: {exc}")
    return _redirect("/ui/users", message=f"Utente creato: {row.username}")


@router.post("/ui/users/{user_id}/update")
def ui_users_update(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    role: str = Form(default=ROLE_VIEWER),
    is_active: str | None = Form(default=None),
) -> RedirectResponse:
    row = db.get(AppUser, user_id)
    if not row:
        return _redirect("/ui/users", error="Utente non trovato.")

    username_clean = username.strip().lower()
    if not username_clean:
        return _redirect("/ui/users", error="Username obbligatorio.")
    duplicate = db.query(AppUser).filter(AppUser.username == username_clean, AppUser.id != user_id).first()
    if duplicate:
        return _redirect("/ui/users", error="Username gia usato da un altro utente.")

    # Evita disattivazione dell'ultimo admin attivo
    new_role = normalize_role(role)
    new_active = _as_bool(is_active)
    if row.role == ROLE_ADMIN and row.is_active and (not new_active or new_role != ROLE_ADMIN):
        admins = (
            db.query(AppUser)
            .filter(AppUser.role == ROLE_ADMIN)
            .filter(AppUser.is_active.is_(True))
            .all()
        )
        if len(admins) <= 1:
            return _redirect("/ui/users", error="Impossibile rimuovere o disattivare l'ultimo admin attivo.")

    row.username = username_clean
    row.role = new_role
    row.is_active = new_active
    row.updated_at = datetime.utcnow()
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return _redirect("/ui/users", error=f"Errore aggiornamento utente: {exc}")

    # se modifico me stesso, riallineo la sessione
    if _session_user_id(request) == user_id:
        request.session["username"] = row.username
        request.session["role"] = row.role

    return _redirect("/ui/users", message=f"Utente aggiornato: {row.username}")


@router.post("/ui/users/{user_id}/password")
def ui_users_password(
    user_id: int,
    db: Session = Depends(get_db),
    new_password: str = Form(...),
) -> RedirectResponse:
    row = db.get(AppUser, user_id)
    if not row:
        return _redirect("/ui/users", error="Utente non trovato.")
    if len(new_password) < 8:
        return _redirect("/ui/users", error="Password troppo corta (minimo 8 caratteri).")
    row.password_hash = hash_password(new_password)
    row.updated_at = datetime.utcnow()
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return _redirect("/ui/users", error=f"Errore aggiornamento password: {exc}")
    return _redirect("/ui/users", message=f"Password aggiornata per {row.username}")


@router.post("/ui/users/{user_id}/delete")
def ui_users_delete(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    row = db.get(AppUser, user_id)
    if not row:
        return _redirect("/ui/users", error="Utente non trovato.")

    current_user_id = _session_user_id(request)
    if current_user_id == user_id:
        return _redirect("/ui/users", error="Non puoi eliminare l'utente con cui sei loggato.")

    if row.role == ROLE_ADMIN and row.is_active:
        admins = (
            db.query(AppUser)
            .filter(AppUser.role == ROLE_ADMIN)
            .filter(AppUser.is_active.is_(True))
            .all()
        )
        if len(admins) <= 1:
            return _redirect("/ui/users", error="Impossibile eliminare l'ultimo admin attivo.")

    try:
        db.delete(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return _redirect("/ui/users", error=f"Errore eliminazione utente: {exc}")
    return _redirect("/ui/users", message=f"Utente eliminato: {row.username}")
