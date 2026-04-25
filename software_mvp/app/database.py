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


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_sqlite_legacy_migrations()
