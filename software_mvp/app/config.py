from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=APP_ROOT / ".env")


def _as_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _default_sqlite_url() -> str:
    return f"sqlite:///{(APP_ROOT / 'configurator.db').as_posix()}"


def _normalize_app_db_url(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    if not value:
        return _default_sqlite_url()
    if value.startswith("sqlite:///./"):
        rel = value[len("sqlite:///./") :]
        return f"sqlite:///{(APP_ROOT / rel).as_posix()}"
    return value


def _default_license_file() -> str:
    return str((APP_ROOT / "license.json").resolve())


def _normalize_local_path(raw_value: str | None, *, default: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return default
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((APP_ROOT / path).resolve())


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_db_url: str
    app_timezone: str
    app_session_secret: str
    app_admin_username: str
    app_admin_password: str
    sqlserver_conn_str: str
    bq_project_id: str
    bq_default_dataset: str
    bq_default_table: str
    bq_location: str
    bq_credentials_file: str
    pipeline_command_timeout_seconds: int
    esyy_product_code: str
    esyy_license_mode: str
    esyy_license_portal_url: str
    esyy_license_check_timeout_seconds: int
    esyy_license_grace_days: int
    esyy_license_file: str


settings = Settings(
    app_name="Esyy B1Connector",
    app_db_url=_normalize_app_db_url(os.getenv("APP_DB_URL")),
    app_timezone=os.getenv("APP_TIMEZONE", "Europe/Rome"),
    app_session_secret=os.getenv("APP_SESSION_SECRET", "change-me-in-production"),
    app_admin_username=os.getenv("APP_ADMIN_USERNAME", "admin"),
    app_admin_password=os.getenv("APP_ADMIN_PASSWORD", "admin123!"),
    sqlserver_conn_str=os.getenv("SQLSERVER_CONN_STR", ""),
    bq_project_id=os.getenv("BQ_PROJECT_ID", ""),
    bq_default_dataset=os.getenv("BQ_DATASET", "sap_reporting"),
    bq_default_table=os.getenv("BQ_TABLE", "stato_ordini_cliente"),
    bq_location=os.getenv("BQ_LOCATION", "EU"),
    bq_credentials_file=os.getenv("BQ_CREDENTIALS_FILE", ""),
    pipeline_command_timeout_seconds=_as_int("PIPELINE_COMMAND_TIMEOUT_SECONDS", 3600),
    esyy_product_code=os.getenv("ESYY_PRODUCT_CODE", "esyy-b1-connector").strip() or "esyy-b1-connector",
    esyy_license_mode=os.getenv("ESYY_LICENSE_MODE", "open_trial").strip().lower() or "open_trial",
    esyy_license_portal_url=os.getenv("ESYY_LICENSE_PORTAL_URL", "").strip(),
    esyy_license_check_timeout_seconds=_as_int("ESYY_LICENSE_CHECK_TIMEOUT_SECONDS", 10),
    esyy_license_grace_days=_as_int("ESYY_LICENSE_GRACE_DAYS", 15),
    esyy_license_file=_normalize_local_path(
        os.getenv("ESYY_LICENSE_FILE"),
        default=_default_license_file(),
    ),
)
