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

        license_rows = conn.exec_driver_sql("PRAGMA table_info(license_states)").fetchall()
        if license_rows:
            license_cols = {row[1] for row in license_rows}

            if "product_code" not in license_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE license_states ADD COLUMN product_code VARCHAR(100) NOT NULL DEFAULT ''"
                )
            if "installation_id" not in license_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE license_states ADD COLUMN installation_id VARCHAR(100) NOT NULL DEFAULT ''"
                )
            if "machine_fingerprint_hash" not in license_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE license_states ADD COLUMN machine_fingerprint_hash VARCHAR(128) NOT NULL DEFAULT ''"
                )
            if "license_key_hash" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN license_key_hash VARCHAR(128)")
            if "license_mode" not in license_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE license_states ADD COLUMN license_mode VARCHAR(40) NOT NULL DEFAULT 'open_trial'"
                )
            if "status" not in license_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE license_states ADD COLUMN status VARCHAR(40) NOT NULL DEFAULT 'open_trial'"
                )
            if "plan" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN plan VARCHAR(100)")
            if "customer_name" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN customer_name VARCHAR(200)")
            if "customer_email" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN customer_email VARCHAR(320)")
            if "valid_until" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN valid_until DATETIME")
            if "grace_until" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN grace_until DATETIME")
            if "last_check_at" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN last_check_at DATETIME")
            if "next_check_at" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN next_check_at DATETIME")
            if "portal_url" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN portal_url VARCHAR(500)")
            if "features_json" not in license_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE license_states ADD COLUMN features_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "message" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN message TEXT")
            if "created_at" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN created_at DATETIME")
            if "updated_at" not in license_cols:
                conn.exec_driver_sql("ALTER TABLE license_states ADD COLUMN updated_at DATETIME")

            conn.exec_driver_sql(
                "UPDATE license_states SET product_code = '' WHERE product_code IS NULL"
            )
            conn.exec_driver_sql(
                "UPDATE license_states SET installation_id = '' WHERE installation_id IS NULL"
            )
            conn.exec_driver_sql(
                "UPDATE license_states SET machine_fingerprint_hash = '' WHERE machine_fingerprint_hash IS NULL"
            )
            conn.exec_driver_sql(
                "UPDATE license_states SET license_mode = 'open_trial' "
                "WHERE license_mode IS NULL OR TRIM(license_mode) = ''"
            )
            conn.exec_driver_sql(
                "UPDATE license_states SET status = 'open_trial' "
                "WHERE status IS NULL OR TRIM(status) = ''"
            )
            conn.exec_driver_sql(
                "UPDATE license_states SET features_json = '{}' "
                "WHERE features_json IS NULL OR TRIM(features_json) = ''"
            )
            conn.exec_driver_sql(
                "UPDATE license_states SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
            )
            conn.exec_driver_sql(
                "UPDATE license_states SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
            )
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_license_state_product_code "
                "ON license_states (product_code)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_license_states_status ON license_states (status)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_license_states_mode ON license_states (license_mode)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_license_states_installation_id ON license_states (installation_id)"
            )

        license_log_rows = conn.exec_driver_sql("PRAGMA table_info(license_check_logs)").fetchall()
        if license_log_rows:
            license_log_cols = {row[1] for row in license_log_rows}

            if "checked_at" not in license_log_cols:
                conn.exec_driver_sql("ALTER TABLE license_check_logs ADD COLUMN checked_at DATETIME")
            if "status" not in license_log_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE license_check_logs ADD COLUMN status VARCHAR(40) NOT NULL DEFAULT 'open_trial'"
                )
            if "mode" not in license_log_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE license_check_logs ADD COLUMN mode VARCHAR(40) NOT NULL DEFAULT 'open_trial'"
                )
            if "success" not in license_log_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE license_check_logs ADD COLUMN success BOOLEAN NOT NULL DEFAULT 1"
                )
            if "message" not in license_log_cols:
                conn.exec_driver_sql("ALTER TABLE license_check_logs ADD COLUMN message TEXT")
            if "response_json" not in license_log_cols:
                conn.exec_driver_sql("ALTER TABLE license_check_logs ADD COLUMN response_json TEXT")

            conn.exec_driver_sql(
                "UPDATE license_check_logs SET checked_at = CURRENT_TIMESTAMP WHERE checked_at IS NULL"
            )
            conn.exec_driver_sql(
                "UPDATE license_check_logs SET status = 'open_trial' "
                "WHERE status IS NULL OR TRIM(status) = ''"
            )
            conn.exec_driver_sql(
                "UPDATE license_check_logs SET mode = 'open_trial' "
                "WHERE mode IS NULL OR TRIM(mode) = ''"
            )
            conn.exec_driver_sql(
                "UPDATE license_check_logs SET success = 1 WHERE success IS NULL"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_license_check_logs_checked_at "
                "ON license_check_logs (checked_at)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_license_check_logs_status "
                "ON license_check_logs (status)"
            )


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_sqlite_legacy_migrations()
