from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(20), default="viewer", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ReportView(Base):
    __tablename__ = "report_views"
    __table_args__ = (
        UniqueConstraint("tenant_code", "schema_name", "view_name", name="uq_view_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_code: Mapped[str] = mapped_column(String(100), default="default", index=True)
    schema_name: Mapped[str] = mapped_column(String(100), default="dbo")
    view_name: Mapped[str] = mapped_column(String(200))
    select_sql: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    pipelines: Mapped[list["Pipeline"]] = relationship(back_populates="source_view")


class Pipeline(Base):
    __tablename__ = "pipelines"
    __table_args__ = (
        UniqueConstraint("tenant_code", "name", name="uq_pipeline_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_code: Mapped[str] = mapped_column(String(100), default="default", index=True)
    name: Mapped[str] = mapped_column(String(200))
    source_view_id: Mapped[int | None] = mapped_column(ForeignKey("report_views.id"), nullable=True)
    bq_dataset: Mapped[str] = mapped_column(String(200), default="sap_reporting")
    bq_table: Mapped[str] = mapped_column(String(200), default="stato_ordini_cliente")
    write_mode: Mapped[str] = mapped_column(String(50), default="WRITE_TRUNCATE")
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    source_view: Mapped[ReportView | None] = relationship(back_populates="pipelines")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="pipeline", cascade="all, delete-orphan")
    run_logs: Mapped[list["RunLog"]] = relationship(back_populates="pipeline", cascade="all, delete-orphan")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"))
    cron_expression: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(100), default="Europe/Rome")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    pipeline: Mapped[Pipeline] = relationship(back_populates="schedules")


class ACLRule(Base):
    __tablename__ = "acl_rules"
    __table_args__ = (
        UniqueConstraint("tenant_code", "user_email", "customer_code", name="uq_acl_rule"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_code: Mapped[str] = mapped_column(String(100), default="default", index=True)
    user_email: Mapped[str] = mapped_column(String(320), index=True)
    customer_code: Mapped[str] = mapped_column(String(100), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ACLFilterRule(Base):
    __tablename__ = "acl_filter_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_code",
            "view_id",
            "user_email",
            "field_name",
            "operator",
            "field_value",
            name="uq_acl_filter_rule",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_code: Mapped[str] = mapped_column(String(100), default="default", index=True)
    view_id: Mapped[int] = mapped_column(ForeignKey("report_views.id"), index=True)
    user_email: Mapped[str] = mapped_column(String(320), index=True)
    field_name: Mapped[str] = mapped_column(String(200), default="")
    operator: Mapped[str] = mapped_column(String(40), default="EQ")
    field_value: Mapped[str] = mapped_column(Text, default="")
    is_master: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="OK")
    rows_extracted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_loaded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    pipeline: Mapped[Pipeline] = relationship(back_populates="run_logs")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class WizardSession(Base):
    __tablename__ = "wizard_sessions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "wizard_id", "user_id", name="uq_wizard_session_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), default="default", index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    wizard_id: Mapped[str] = mapped_column(String(100), index=True)
    current_step_id: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(40), default="not_started", index=True)
    draft_data_json: Mapped[str] = mapped_column(Text, default="{}")
    last_test_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
