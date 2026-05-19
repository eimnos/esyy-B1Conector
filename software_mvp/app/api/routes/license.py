from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...deps import get_db
from ...services.auth_service import ROLE_ADMIN, ROLE_OPERATOR
from ...services.license_service import (
    activate_open_trial,
    check_license,
    get_license_status,
    reset_local_state,
    should_block_app,
)

router = APIRouter(prefix="/api/license", tags=["license"])


class ActivateOpenTrialPayload(BaseModel):
    customer_name: str | None = None
    customer_email: str | None = None


def _ensure_write_role(request: Request) -> None:
    current_user = getattr(request.state, "current_user", None)
    if not isinstance(current_user, dict):
        raise HTTPException(status_code=401, detail="Autenticazione richiesta.")
    role = str(current_user.get("role") or "").strip().lower()
    if role not in {ROLE_ADMIN, ROLE_OPERATOR}:
        raise HTTPException(status_code=403, detail="Permesso negato.")


def _status_payload(db: Session) -> dict[str, Any]:
    payload = get_license_status(db)
    payload["blocking_enabled"] = False
    payload["should_block_app"] = should_block_app(db)
    return payload


@router.get("/status")
def api_license_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    return _status_payload(db)


@router.post("/activate-open-trial")
def api_license_activate_open_trial(
    request: Request,
    payload: ActivateOpenTrialPayload | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_write_role(request)
    activate_open_trial(
        db,
        customer_name=(payload.customer_name if payload else None),
        customer_email=(payload.customer_email if payload else None),
    )
    return _status_payload(db)


@router.post("/check")
def api_license_check(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure_write_role(request)
    check_license(db)
    return _status_payload(db)


@router.post("/reset-local")
def api_license_reset_local(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure_write_role(request)
    reset_local_state(db)
    return _status_payload(db)
