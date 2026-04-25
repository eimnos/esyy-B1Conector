from __future__ import annotations

import re
from dataclasses import dataclass

import pyodbc

from ..config import settings
from ..database import SessionLocal
from ..models import AppSetting

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SQLSERVER_CONN_STR_SETTING_KEY = "sqlserver_conn_str"


class SQLServerPublishError(Exception):
    pass


@dataclass(frozen=True)
class SQLServerPublishResult:
    server_name: str
    db_name: str
    schema_name: str
    view_name: str


def _validate_identifier(value: str, label: str) -> str:
    clean_value = value.strip()
    if not _IDENTIFIER_RE.match(clean_value):
        raise SQLServerPublishError(f"{label} non valido: {value!r}")
    return clean_value


def _get_saved_conn_str() -> str | None:
    db = SessionLocal()
    try:
        row = db.get(AppSetting, SQLSERVER_CONN_STR_SETTING_KEY)
        if not row:
            return None
        value = (row.value or "").strip()
        return value or None
    finally:
        db.close()


def get_effective_sqlserver_conn_str() -> str:
    runtime_value = _get_saved_conn_str()
    if runtime_value:
        return runtime_value
    return (settings.sqlserver_conn_str or "").strip()


def test_sqlserver_connection(conn_str: str | None = None) -> tuple[str, str]:
    value = (conn_str or "").strip() or get_effective_sqlserver_conn_str()
    if not value:
        raise SQLServerPublishError(
            "Connessione SQL Server non configurata. Impostala in Settings o nel file .env (SQLSERVER_CONN_STR)."
        )
    try:
        cnxn = pyodbc.connect(value, timeout=8)
        try:
            cursor = cnxn.cursor()
            cursor.execute("SELECT @@SERVERNAME AS server_name, DB_NAME() AS db_name")
            row = cursor.fetchone()
            server_name = str(row[0]) if row and len(row) >= 1 else "n/a"
            db_name = str(row[1]) if row and len(row) >= 2 else "n/a"
            return server_name, db_name
        finally:
            cnxn.close()
    except pyodbc.Error as exc:
        raise SQLServerPublishError(str(exc)) from exc


def publish_view(schema_name: str, view_name: str, select_sql: str) -> SQLServerPublishResult:
    conn_str = get_effective_sqlserver_conn_str()
    if not conn_str:
        raise SQLServerPublishError(
            "Connessione SQL Server non configurata. Impostala in Settings o nel file .env (SQLSERVER_CONN_STR)."
        )

    schema_clean = _validate_identifier(schema_name, "schema_name")
    view_clean = _validate_identifier(view_name, "view_name")
    body = select_sql.strip()

    lower_body = body.lower()
    if not (lower_body.startswith("select") or lower_body.startswith("with")):
        raise SQLServerPublishError("La query della view deve iniziare con SELECT o WITH")

    statement = f"CREATE OR ALTER VIEW [{schema_clean}].[{view_clean}] AS\n{body}"

    try:
        cnxn = pyodbc.connect(conn_str, timeout=8)
        try:
            cursor = cnxn.cursor()
            cursor.execute(statement)
            cnxn.commit()

            cursor.execute("SELECT @@SERVERNAME AS server_name, DB_NAME() AS db_name")
            row = cursor.fetchone()
            server_name = str(row[0]) if row and len(row) >= 1 else "n/a"
            db_name = str(row[1]) if row and len(row) >= 2 else "n/a"

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM sys.views v
                JOIN sys.schemas s ON s.schema_id = v.schema_id
                WHERE s.name = ? AND v.name = ?
                """,
                (schema_clean, view_clean),
            )
            exists_count = int(cursor.fetchone()[0])
            if exists_count <= 0:
                raise SQLServerPublishError(
                    f"Publish eseguita ma vista non trovata in metadata SQL Server: {schema_clean}.{view_clean}"
                )
            return SQLServerPublishResult(
                server_name=server_name,
                db_name=db_name,
                schema_name=schema_clean,
                view_name=view_clean,
            )
        finally:
            cnxn.close()
    except pyodbc.Error as exc:
        raise SQLServerPublishError(str(exc)) from exc
