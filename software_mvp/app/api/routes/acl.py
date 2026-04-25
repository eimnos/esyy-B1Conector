from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...deps import get_db
from ...models import ACLRule, ReportView
from ...schemas import ACLRuleCreate, ACLRuleRead, ACLRuleUpdate
from ...services.bigquery_service import BigQueryServiceError, sync_acl_rules_to_bigquery
from ...services.source_db_metadata_service import SourceDBMetadataError, describe_select_columns

router = APIRouter(prefix="/api/acl", tags=["acl"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[ACLRuleRead])
def list_acl_rules(
    tenant_code: str = Query(default="default"),
    db: Session = Depends(get_db),
) -> list[ACLRule]:
    return (
        db.query(ACLRule)
        .filter(ACLRule.tenant_code == tenant_code)
        .order_by(ACLRule.user_email.asc(), ACLRule.customer_code.asc())
        .all()
    )


@router.get("/masters", response_model=list[ACLRuleRead])
def list_master_users(
    tenant_code: str = Query(default="default"),
    db: Session = Depends(get_db),
) -> list[ACLRule]:
    return (
        db.query(ACLRule)
        .filter(ACLRule.tenant_code == tenant_code)
        .filter(ACLRule.customer_code == "__ALL__")
        .filter(ACLRule.is_active.is_(True))
        .order_by(ACLRule.user_email.asc())
        .all()
    )


@router.post("", response_model=ACLRuleRead)
def create_acl_rule(payload: ACLRuleCreate, db: Session = Depends(get_db)) -> ACLRule:
    row = ACLRule(
        tenant_code=payload.tenant_code,
        user_email=payload.user_email.lower().strip(),
        customer_code=payload.customer_code.strip(),
        is_active=payload.is_active,
        note=payload.note,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Regola ACL duplicata o non valida: {exc}") from exc
    try:
        sync_acl_rules_to_bigquery(db)
    except BigQueryServiceError as exc:  # best effort
        logger.warning("ACL create: sync BigQuery non riuscita: %s", exc)
    db.refresh(row)
    return row


@router.put("/{rule_id}", response_model=ACLRuleRead)
def update_acl_rule(rule_id: int, payload: ACLRuleUpdate, db: Session = Depends(get_db)) -> ACLRule:
    row = db.get(ACLRule, rule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Regola ACL non trovata")

    data = payload.model_dump(exclude_unset=True)
    if "user_email" in data and data["user_email"] is not None:
        data["user_email"] = data["user_email"].lower().strip()
    if "customer_code" in data and data["customer_code"] is not None:
        data["customer_code"] = data["customer_code"].strip()

    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Errore aggiornamento ACL: {exc}") from exc
    try:
        sync_acl_rules_to_bigquery(db)
    except BigQueryServiceError as exc:  # best effort
        logger.warning("ACL update: sync BigQuery non riuscita: %s", exc)
    db.refresh(row)
    return row


@router.delete("/{rule_id}")
def delete_acl_rule(rule_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    row = db.get(ACLRule, rule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Regola ACL non trovata")
    db.delete(row)
    db.commit()
    try:
        sync_acl_rules_to_bigquery(db)
    except BigQueryServiceError as exc:  # best effort
        logger.warning("ACL delete: sync BigQuery non riuscita: %s", exc)
    return {"status": "deleted"}


@router.get("/view-columns")
def acl_view_columns(view_id: int = Query(...), db: Session = Depends(get_db)) -> dict:
    row = db.get(ReportView, view_id)
    if not row:
        raise HTTPException(status_code=404, detail="View non trovata.")
    try:
        payload = describe_select_columns(db, row.select_sql)
    except SourceDBMetadataError as exc:
        raise HTTPException(status_code=400, detail=f"Impossibile leggere colonne view: {exc}") from exc
    return {
        "view_id": row.id,
        "view_name": row.view_name,
        "engine": payload.get("engine", "sqlserver"),
        "columns": payload.get("columns", []),
    }
