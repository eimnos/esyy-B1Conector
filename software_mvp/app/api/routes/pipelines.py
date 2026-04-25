from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...deps import get_db
from ...models import Pipeline, RunLog
from ...schemas import PipelineCreate, PipelineRead, PipelineUpdate, RunLogRead
from ...services.pipeline_service import run_pipeline

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


@router.get("", response_model=list[PipelineRead])
def list_pipelines(db: Session = Depends(get_db)) -> list[Pipeline]:
    return db.query(Pipeline).order_by(Pipeline.id.desc()).all()


@router.post("", response_model=PipelineRead)
def create_pipeline(payload: PipelineCreate, db: Session = Depends(get_db)) -> Pipeline:
    row = Pipeline(**payload.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Pipeline duplicata o non valida: {exc}") from exc
    db.refresh(row)
    return row


@router.put("/{pipeline_id}", response_model=PipelineRead)
def update_pipeline(
    pipeline_id: int,
    payload: PipelineUpdate,
    db: Session = Depends(get_db),
) -> Pipeline:
    row = db.get(Pipeline, pipeline_id)
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline non trovata")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Errore aggiornamento pipeline: {exc}") from exc
    db.refresh(row)
    return row


@router.post("/{pipeline_id}/run", response_model=RunLogRead)
def run_pipeline_now(pipeline_id: int, db: Session = Depends(get_db)) -> RunLog:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline non trovata")
    return run_pipeline(db, pipeline)


@router.get("/{pipeline_id}/runs", response_model=list[RunLogRead])
def list_pipeline_runs(pipeline_id: int, db: Session = Depends(get_db)) -> list[RunLog]:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline non trovata")

    return (
        db.query(RunLog)
        .filter(RunLog.pipeline_id == pipeline_id)
        .order_by(RunLog.id.desc())
        .limit(100)
        .all()
    )
