from __future__ import annotations

import os
from typing import Any

import pyodbc
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AppSetting
from .sqlserver_service import SQLSERVER_CONN_STR_SETTING_KEY

SOURCE_DB_ENGINE_SETTING_KEY = "source_db_engine"
HANA_CONN_STR_SETTING_KEY = "hana_conn_str"
SUPPORTED_ENGINES = {"sqlserver", "hana"}


class SourceDBMetadataError(Exception):
    pass


def _load_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppSetting, key)
    if not row:
        return default
    return (row.value or "").strip() or default


def get_effective_source_engine(db: Session) -> str:
    value = _load_setting(db, SOURCE_DB_ENGINE_SETTING_KEY, default="sqlserver").strip().lower()
    if value not in SUPPORTED_ENGINES:
        return "sqlserver"
    return value


def _get_effective_conn_str(db: Session, engine: str) -> str:
    if engine == "sqlserver":
        runtime_value = _load_setting(db, SQLSERVER_CONN_STR_SETTING_KEY, default="")
        return runtime_value or (settings.sqlserver_conn_str or "").strip()

    runtime_value = _load_setting(db, HANA_CONN_STR_SETTING_KEY, default="")
    return runtime_value or os.getenv("HANA_CONN_STR", "").strip()


def _open_connection(db: Session, engine: str | None = None) -> tuple[str, pyodbc.Connection]:
    selected_engine = (engine or get_effective_source_engine(db)).strip().lower()
    if selected_engine not in SUPPORTED_ENGINES:
        raise SourceDBMetadataError(
            f"Engine sorgente non supportato: {selected_engine}. Valori ammessi: sqlserver, hana."
        )

    conn_str = _get_effective_conn_str(db, selected_engine)
    if not conn_str:
        if selected_engine == "hana":
            raise SourceDBMetadataError(
                "Connessione HANA non configurata. Configurala in Settings (wizard DB) o in HANA_CONN_STR."
            )
        raise SourceDBMetadataError(
            "Connessione SQL Server non configurata. Configurala in Settings o nel file .env (SQLSERVER_CONN_STR)."
        )

    try:
        conn = pyodbc.connect(conn_str, timeout=8)
    except pyodbc.Error as exc:
        raise SourceDBMetadataError(str(exc)) from exc
    return selected_engine, conn


def list_objects(db: Session, search: str = "", limit: int = 200) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 500))
    search_clean = (search or "").strip()

    engine, conn = _open_connection(db)
    try:
        cursor = conn.cursor()
        if engine == "sqlserver":
            query = f"""
SELECT TOP {safe_limit}
    TABLE_SCHEMA AS schema_name,
    TABLE_NAME AS object_name,
    CASE
      WHEN TABLE_TYPE = 'BASE TABLE' THEN 'TABLE'
      ELSE TABLE_TYPE
    END AS object_type
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
  AND (
      ? = ''
      OR TABLE_NAME LIKE ?
      OR TABLE_SCHEMA LIKE ?
  )
ORDER BY TABLE_SCHEMA, TABLE_NAME;
"""
            like_value = f"%{search_clean}%"
            cursor.execute(query, search_clean, like_value, like_value)
        else:
            # SAP HANA: tables + views da catalogo SYS.
            query = f"""
SELECT schema_name, object_name, object_type
FROM (
    SELECT
        SCHEMA_NAME AS schema_name,
        TABLE_NAME AS object_name,
        'TABLE' AS object_type
    FROM SYS.TABLES
    UNION ALL
    SELECT
        SCHEMA_NAME AS schema_name,
        VIEW_NAME AS object_name,
        'VIEW' AS object_type
    FROM SYS.VIEWS
) AS src
WHERE schema_name NOT LIKE 'SYS%'
  AND schema_name <> '_SYS_REPO'
  AND (
      ? = ''
      OR UPPER(object_name) LIKE ?
      OR UPPER(schema_name) LIKE ?
  )
ORDER BY schema_name, object_name
LIMIT {safe_limit};
"""
            like_value = f"%{search_clean.upper()}%"
            cursor.execute(query, search_clean, like_value, like_value)

        rows = []
        for raw in cursor.fetchall():
            rows.append(
                {
                    "schema_name": str(raw[0]),
                    "object_name": str(raw[1]),
                    "object_type": str(raw[2]),
                }
            )
        return {"engine": engine, "objects": rows}
    except pyodbc.Error as exc:
        raise SourceDBMetadataError(str(exc)) from exc
    finally:
        conn.close()


def list_columns(db: Session, schema_name: str, object_name: str) -> dict[str, Any]:
    schema_clean = (schema_name or "").strip()
    object_clean = (object_name or "").strip()
    if not schema_clean or not object_clean:
        raise SourceDBMetadataError("schema_name e object_name sono obbligatori.")

    engine, conn = _open_connection(db)
    try:
        cursor = conn.cursor()
        if engine == "sqlserver":
            query = """
SELECT
    COLUMN_NAME,
    DATA_TYPE,
    ORDINAL_POSITION
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = ?
  AND TABLE_NAME = ?
ORDER BY ORDINAL_POSITION;
"""
            cursor.execute(query, schema_clean, object_clean)
            fetched = cursor.fetchall()
        else:
            # SAP HANA: prova prima TABLE_COLUMNS, poi VIEW_COLUMNS.
            query_table = """
SELECT
    COLUMN_NAME,
    DATA_TYPE_NAME,
    POSITION
FROM SYS.TABLE_COLUMNS
WHERE SCHEMA_NAME = ?
  AND TABLE_NAME = ?
ORDER BY POSITION;
"""
            cursor.execute(query_table, schema_clean, object_clean)
            fetched = cursor.fetchall()
            if not fetched:
                query_view = """
SELECT
    COLUMN_NAME,
    DATA_TYPE_NAME,
    POSITION
FROM SYS.VIEW_COLUMNS
WHERE SCHEMA_NAME = ?
  AND VIEW_NAME = ?
ORDER BY POSITION;
"""
                cursor.execute(query_view, schema_clean, object_clean)
                fetched = cursor.fetchall()

        rows = []
        for raw in fetched:
            rows.append(
                {
                    "column_name": str(raw[0]),
                    "data_type": str(raw[1]),
                    "position": int(raw[2]),
                }
            )
        return {"engine": engine, "schema_name": schema_clean, "object_name": object_clean, "columns": rows}
    except pyodbc.Error as exc:
        raise SourceDBMetadataError(str(exc)) from exc
    finally:
        conn.close()


def describe_select_columns(db: Session, select_sql: str) -> dict[str, Any]:
    query = (select_sql or "").strip().rstrip(";")
    if not query:
        raise SourceDBMetadataError("SELECT SQL vuota.")

    engine, conn = _open_connection(db)
    try:
        cursor = conn.cursor()
        if engine == "sqlserver":
            wrapped = f"SELECT TOP 0 * FROM ({query}) AS src"
        else:
            wrapped = f"SELECT * FROM ({query}) AS src WHERE 1=0"
        cursor.execute(wrapped)
        columns = []
        if cursor.description:
            for pos, col in enumerate(cursor.description, start=1):
                col_name = str(col[0])
                col_type = str(col[1]) if len(col) > 1 and col[1] is not None else ""
                columns.append(
                    {
                        "column_name": col_name,
                        "data_type": col_type,
                        "position": pos,
                    }
                )
        return {"engine": engine, "columns": columns}
    except pyodbc.Error as exc:
        raise SourceDBMetadataError(str(exc)) from exc
    finally:
        conn.close()
