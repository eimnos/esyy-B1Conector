from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ReportViewCreate(BaseModel):
    tenant_code: str = "default"
    schema_name: str = "dbo"
    view_name: str
    select_sql: str
    is_active: bool = True


class ReportViewUpdate(BaseModel):
    schema_name: str | None = None
    view_name: str | None = None
    select_sql: str | None = None
    is_active: bool | None = None


class ReportViewRead(ORMBaseModel):
    id: int
    tenant_code: str
    schema_name: str
    view_name: str
    select_sql: str
    version: int
    is_active: bool
    last_published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PipelineCreate(BaseModel):
    tenant_code: str = "default"
    name: str
    source_view_id: int | None = None
    bq_dataset: str = "sap_reporting"
    bq_table: str = "stato_ordini_cliente"
    write_mode: str = "WRITE_TRUNCATE"
    command: str | None = None
    is_active: bool = True


class PipelineUpdate(BaseModel):
    name: str | None = None
    source_view_id: int | None = None
    bq_dataset: str | None = None
    bq_table: str | None = None
    write_mode: str | None = None
    command: str | None = None
    is_active: bool | None = None


class PipelineRead(ORMBaseModel):
    id: int
    tenant_code: str
    name: str
    source_view_id: int | None
    bq_dataset: str
    bq_table: str
    write_mode: str
    command: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ScheduleCreate(BaseModel):
    pipeline_id: int
    cron_expression: str = Field(..., description="Formato cron 5 campi")
    timezone: str = "Europe/Rome"
    is_active: bool = True


class ScheduleUpdate(BaseModel):
    cron_expression: str | None = None
    timezone: str | None = None
    is_active: bool | None = None


class ScheduleRead(ORMBaseModel):
    id: int
    pipeline_id: int
    cron_expression: str
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ACLRuleCreate(BaseModel):
    tenant_code: str = "default"
    user_email: str
    customer_code: str
    is_active: bool = True
    note: str | None = None


class ACLRuleUpdate(BaseModel):
    user_email: str | None = None
    customer_code: str | None = None
    is_active: bool | None = None
    note: str | None = None


class ACLRuleRead(ORMBaseModel):
    id: int
    tenant_code: str
    user_email: str
    customer_code: str
    is_active: bool
    note: str | None
    created_at: datetime
    updated_at: datetime


class RunLogRead(ORMBaseModel):
    id: int
    pipeline_id: int
    started_at: datetime
    ended_at: datetime | None
    status: str
    rows_extracted: int | None
    rows_loaded: int | None
    message: str | None
