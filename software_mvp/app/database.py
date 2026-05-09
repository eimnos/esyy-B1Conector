from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


connect_args: dict[str, object] = {}
if settings.app_db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.app_db_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _run_sqlite_legacy_migrations() -> None:
    if not settings.app_db_url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(app_users)").fetchall()
        if not rows:
            return

        cols = {row[1] for row in rows}

        if "role" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE app_users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'viewer'"
            )
        if "is_active" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE app_users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
            )
        if "created_at" not in cols:
            conn.exec_driver_sql("ALTER TABLE app_users ADD COLUMN created_at DATETIME")
            conn.exec_driver_sql(
                "UPDATE app_users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
            )
        if "updated_at" not in cols:
            conn.exec_driver_sql("ALTER TABLE app_users ADD COLUMN updated_at DATETIME")
            conn.exec_driver_sql(
                "UPDATE app_users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
            )

        conn.exec_driver_sql("UPDATE app_users SET role = 'viewer' WHERE role IS NULL OR TRIM(role) = ''")
        conn.exec_driver_sql("UPDATE app_users SET is_active = 1 WHERE is_active IS NULL")

        wizard_rows = conn.exec_driver_sql("PRAGMA table_info(wizard_sessions)").fetchall()
        if wizard_rows:
            wizard_cols = {row[1] for row in wizard_rows}

            if "tenant_id" not in wizard_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE wizard_sessions ADD COLUMN tenant_id VARCHAR(100) NOT NULL DEFAULT 'default'"
                )
            if "user_id" not in wizard_cols:
                conn.exec_driver_sql("ALTER TABLE wizard_sessions ADD COLUMN user_id INTEGER")
            if "wizard_id" not in wizard_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE wizard_sessions ADD COLUMN wizard_id VARCHAR(100) NOT NULL DEFAULT ''"
                )
            if "current_step_id" not in wizard_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE wizard_sessions ADD COLUMN current_step_id VARCHAR(100) NOT NULL DEFAULT ''"
                )
            if "status" not in wizard_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE wizard_sessions ADD COLUMN status VARCHAR(40) NOT NULL DEFAULT 'not_started'"
                )
            if "draft_data_json" not in wizard_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE wizard_sessions ADD COLUMN draft_data_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "last_test_status" not in wizard_cols:
                conn.exec_driver_sql("ALTER TABLE wizard_sessions ADD COLUMN last_test_status VARCHAR(40)")
            if "last_test_message" not in wizard_cols:
                conn.exec_driver_sql("ALTER TABLE wizard_sessions ADD COLUMN last_test_message TEXT")
            if "completed_at" not in wizard_cols:
                conn.exec_driver_sql("ALTER TABLE wizard_sessions ADD COLUMN completed_at DATETIME")
            if "created_at" not in wizard_cols:
                conn.exec_driver_sql("ALTER TABLE wizard_sessions ADD COLUMN created_at DATETIME")
            if "updated_at" not in wizard_cols:
                conn.exec_driver_sql("ALTER TABLE wizard_sessions ADD COLUMN updated_at DATETIME")

            conn.exec_driver_sql(
                "UPDATE wizard_sessions SET tenant_id = 'default' WHERE tenant_id IS NULL OR TRIM(tenant_id) = ''"
            )
            conn.exec_driver_sql(
                "UPDATE wizard_sessions SET wizard_id = '' WHERE wizard_id IS NULL"
            )
            conn.exec_driver_sql(
                "UPDATE wizard_sessions SET current_step_id = '' WHERE current_step_id IS NULL"
            )
            conn.exec_driver_sql(
                "UPDATE wizard_sessions SET status = 'not_started' "
                "WHERE status IS NULL OR TRIM(status) = ''"
            )
            conn.exec_driver_sql(
                "UPDATE wizard_sessions SET draft_data_json = '{}' "
                "WHERE draft_data_json IS NULL OR TRIM(draft_data_json) = ''"
            )
            conn.exec_driver_sql(
                "UPDATE wizard_sessions SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
            )
            conn.exec_driver_sql(
                "UPDATE wizard_sessions SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
            )
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_wizard_session_scope "
                "ON wizard_sessions (tenant_id, wizard_id, user_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_wizard_sessions_tenant_id ON wizard_sessions (tenant_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_wizard_sessions_wizard_id ON wizard_sessions (wizard_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_wizard_sessions_status ON wizard_sessions (status)"
            )


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_sqlite_legacy_migrations()
