from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...deps import get_db
from ...models import ACLRule, Pipeline, ReportView, RunLog, Schedule

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict[str, int]:
    return {
        "views": db.query(func.count(ReportView.id)).scalar() or 0,
        "pipelines": db.query(func.count(Pipeline.id)).scalar() or 0,
        "schedules": db.query(func.count(Schedule.id)).scalar() or 0,
        "acl_rules": db.query(func.count(ACLRule.id)).scalar() or 0,
        "run_logs": db.query(func.count(RunLog.id)).scalar() or 0,
    }
