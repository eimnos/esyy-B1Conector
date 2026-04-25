from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Pipeline, ReportView, RunLog
from .bigquery_service import BigQueryServiceError, run_pipeline_sql_to_bigquery


@dataclass
class PipelineExecutionResult:
    started_at: datetime
    ended_at: datetime
    status: str
    message: str
    exit_code: int | None
    rows_extracted: int | None
    rows_loaded: int | None


def _run_command(command: str | None) -> PipelineExecutionResult:
    started_at = datetime.utcnow()

    if not command or not command.strip():
        ended_at = datetime.utcnow()
        return PipelineExecutionResult(
            started_at=started_at,
            ended_at=ended_at,
            status="OK",
            message="Nessun comando configurato: run no-op.",
            exit_code=0,
            rows_extracted=0,
            rows_loaded=0,
        )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=settings.pipeline_command_timeout_seconds,
            check=False,
        )
        ended_at = datetime.utcnow()
        status = "OK" if result.returncode == 0 else "ERROR"
        message = (
            f"Command exit code: {result.returncode}\n"
            f"STDOUT:\n{result.stdout.strip()}\n"
            f"STDERR:\n{result.stderr.strip()}"
        )
        return PipelineExecutionResult(
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            message=message,
            exit_code=result.returncode,
            rows_extracted=None,
            rows_loaded=None,
        )
    except subprocess.TimeoutExpired as exc:
        ended_at = datetime.utcnow()
        return PipelineExecutionResult(
            started_at=started_at,
            ended_at=ended_at,
            status="ERROR",
            message=f"Timeout comando pipeline: {exc}",
            exit_code=None,
            rows_extracted=None,
            rows_loaded=None,
        )
    except Exception as exc:  # noqa: BLE001
        ended_at = datetime.utcnow()
        return PipelineExecutionResult(
            started_at=started_at,
            ended_at=ended_at,
            status="ERROR",
            message=f"Errore esecuzione pipeline: {exc}",
            exit_code=None,
            rows_extracted=None,
            rows_loaded=None,
        )


def _run_managed_pipeline(db: Session, pipeline: Pipeline) -> PipelineExecutionResult:
    started_at = datetime.utcnow()

    if not pipeline.source_view_id:
        ended_at = datetime.utcnow()
        return PipelineExecutionResult(
            started_at=started_at,
            ended_at=ended_at,
            status="ERROR",
            message=(
                "Managed mode richiede source_view_id valorizzato. "
                "In alternativa configura un comando custom."
            ),
            exit_code=None,
            rows_extracted=None,
            rows_loaded=None,
        )

    view = db.get(ReportView, pipeline.source_view_id)
    if not view:
        ended_at = datetime.utcnow()
        return PipelineExecutionResult(
            started_at=started_at,
            ended_at=ended_at,
            status="ERROR",
            message=f"View sorgente non trovata (ID={pipeline.source_view_id}).",
            exit_code=None,
            rows_extracted=None,
            rows_loaded=None,
        )

    try:
        result = run_pipeline_sql_to_bigquery(db, pipeline, view)
        ended_at = datetime.utcnow()
        return PipelineExecutionResult(
            started_at=started_at,
            ended_at=ended_at,
            status="OK",
            message=result.message,
            exit_code=0,
            rows_extracted=result.rows_extracted,
            rows_loaded=result.rows_loaded,
        )
    except BigQueryServiceError as exc:
        ended_at = datetime.utcnow()
        return PipelineExecutionResult(
            started_at=started_at,
            ended_at=ended_at,
            status="ERROR",
            message=str(exc),
            exit_code=None,
            rows_extracted=None,
            rows_loaded=None,
        )
    except Exception as exc:  # noqa: BLE001
        ended_at = datetime.utcnow()
        return PipelineExecutionResult(
            started_at=started_at,
            ended_at=ended_at,
            status="ERROR",
            message=f"Errore managed pipeline: {exc}",
            exit_code=None,
            rows_extracted=None,
            rows_loaded=None,
        )


def run_pipeline(db: Session, pipeline: Pipeline) -> RunLog:
    command = (pipeline.command or "").strip()
    if command:
        execution = _run_command(command)
    else:
        execution = _run_managed_pipeline(db, pipeline)

    run_log = RunLog(
        pipeline_id=pipeline.id,
        started_at=execution.started_at,
        ended_at=execution.ended_at,
        status=execution.status,
        rows_extracted=execution.rows_extracted,
        rows_loaded=execution.rows_loaded,
        message=execution.message,
    )
    db.add(run_log)
    db.commit()
    db.refresh(run_log)
    return run_log
