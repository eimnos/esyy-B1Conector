from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...deps import get_db
from ...models import Pipeline, Schedule
from ...schemas import ScheduleCreate, ScheduleRead, ScheduleUpdate
from ...services.scheduler_service import reload_jobs, validate_cron_expression

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleRead])
def list_schedules(db: Session = Depends(get_db)) -> list[Schedule]:
    return db.query(Schedule).order_by(Schedule.id.desc()).all()


@router.post("", response_model=ScheduleRead)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)) -> Schedule:
    pipeline = db.get(Pipeline, payload.pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline non trovata")

    try:
        validate_cron_expression(payload.cron_expression, payload.timezone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Cron non valido: {exc}") from exc

    row = Schedule(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    reload_jobs()
    return row


@router.put("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
) -> Schedule:
    row = db.get(Schedule, schedule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule non trovata")

    update_data = payload.model_dump(exclude_unset=True)
    cron_to_check = update_data.get("cron_expression", row.cron_expression)
    tz_to_check = update_data.get("timezone", row.timezone)
    try:
        validate_cron_expression(cron_to_check, tz_to_check)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Cron non valido: {exc}") from exc

    for key, value in update_data.items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    reload_jobs()
    return row


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    row = db.get(Schedule, schedule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule non trovata")
    db.delete(row)
    db.commit()
    reload_jobs()
    return {"status": "deleted"}
