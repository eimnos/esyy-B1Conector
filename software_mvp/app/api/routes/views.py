from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...deps import get_db
from ...models import ReportView
from ...schemas import ReportViewCreate, ReportViewRead, ReportViewUpdate
from ...services.sqlserver_service import SQLServerPublishError, publish_view

router = APIRouter(prefix="/api/views", tags=["views"])


@router.get("", response_model=list[ReportViewRead])
def list_views(db: Session = Depends(get_db)) -> list[ReportView]:
    return db.query(ReportView).order_by(ReportView.id.desc()).all()


@router.post("", response_model=ReportViewRead)
def create_view(payload: ReportViewCreate, db: Session = Depends(get_db)) -> ReportView:
    row = ReportView(**payload.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"View duplicata o non valida: {exc}") from exc
    db.refresh(row)
    return row


@router.put("/{view_id}", response_model=ReportViewRead)
def update_view(view_id: int, payload: ReportViewUpdate, db: Session = Depends(get_db)) -> ReportView:
    row = db.get(ReportView, view_id)
    if not row:
        raise HTTPException(status_code=404, detail="View non trovata")

    update_data = payload.model_dump(exclude_unset=True)
    if "select_sql" in update_data and update_data["select_sql"] != row.select_sql:
        row.version += 1

    for key, value in update_data.items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Errore aggiornamento view: {exc}") from exc
    db.refresh(row)
    return row


@router.post("/{view_id}/publish", response_model=ReportViewRead)
def publish_view_to_sqlserver(view_id: int, db: Session = Depends(get_db)) -> ReportView:
    row = db.get(ReportView, view_id)
    if not row:
        raise HTTPException(status_code=404, detail="View non trovata")

    try:
        publish_view(
            schema_name=row.schema_name,
            view_name=row.view_name,
            select_sql=row.select_sql,
        )
    except SQLServerPublishError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row.last_published_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row
