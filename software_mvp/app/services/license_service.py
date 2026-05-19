from __future__ import annotations

import hashlib
import json
import platform
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..models import LicenseCheckLog, LicenseState

LICENSE_MODE_OPEN_TRIAL = "open_trial"
LICENSE_MODE_LOCAL_FILE = "local_file"
LICENSE_MODE_PORTAL = "portal"
LICENSE_MODE_ALLOWED = {
    LICENSE_MODE_OPEN_TRIAL,
    LICENSE_MODE_LOCAL_FILE,
    LICENSE_MODE_PORTAL,
}

LICENSE_STATUS_OPEN_TRIAL = "open_trial"
LICENSE_STATUS_VALID = "valid"
LICENSE_STATUS_WARNING = "warning"
LICENSE_STATUS_EXPIRED = "expired"
LICENSE_STATUS_INVALID = "invalid"
LICENSE_STATUS_PORTAL_UNREACHABLE = "portal_unreachable"
LICENSE_STATUS_NOT_CONFIGURED = "not_configured"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _normalize_mode(value: str | None) -> str:
    clean = (value or "").strip().lower()
    if clean in LICENSE_MODE_ALLOWED:
        return clean
    return LICENSE_MODE_OPEN_TRIAL


def _default_features() -> dict[str, bool]:
    return {
        "sqlserver": True,
        "hana_preparation": True,
        "bigquery_export": True,
        "scheduler": True,
        "acl": True,
        "multi_pipeline": True,
        "ui_admin": True,
    }


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _parse_features(raw: str | None) -> dict[str, bool]:
    fallback = _default_features()
    if not raw:
        return fallback
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return fallback
    if not isinstance(payload, dict):
        return fallback
    for key in list(fallback.keys()):
        if key in payload:
            fallback[key] = bool(payload[key])
    return fallback


def _fingerprint_hash() -> str:
    raw = "|".join(
        [
            platform.node() or "",
            platform.platform() or "",
            platform.machine() or "",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_iso_datetime(raw_value: Any) -> datetime | None:
    if raw_value is None:
        return None
    clean = str(raw_value).strip()
    if not clean:
        return None
    try:
        return datetime.fromisoformat(clean.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _license_file_status() -> tuple[str, bool, str, dict[str, Any]]:
    file_path = Path(settings.esyy_license_file)
    if not file_path.exists():
        return (
            LICENSE_STATUS_NOT_CONFIGURED,
            False,
            f"File licenza non trovato: {file_path}",
            {},
        )
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (
            LICENSE_STATUS_WARNING,
            False,
            f"Impossibile leggere il file licenza locale: {exc}",
            {},
        )
    if not isinstance(payload, dict):
        return (
            LICENSE_STATUS_WARNING,
            False,
            "Formato file licenza non valido: atteso oggetto JSON.",
            {},
        )

    status = str(payload.get("status") or "").strip().lower() or LICENSE_STATUS_VALID
    if status not in {
        LICENSE_STATUS_VALID,
        LICENSE_STATUS_WARNING,
        LICENSE_STATUS_EXPIRED,
        LICENSE_STATUS_INVALID,
        LICENSE_STATUS_OPEN_TRIAL,
        LICENSE_STATUS_PORTAL_UNREACHABLE,
        LICENSE_STATUS_NOT_CONFIGURED,
    }:
        status = LICENSE_STATUS_WARNING

    message = str(payload.get("message") or "").strip() or "File licenza locale letto con successo."
    return status, True, message, payload


def _log_check(
    db: Session,
    *,
    status: str,
    mode: str,
    success: bool,
    message: str,
    response_payload: dict[str, Any] | None,
) -> None:
    row = LicenseCheckLog(
        checked_at=_utcnow(),
        status=status,
        mode=mode,
        success=success,
        message=message,
        response_json=_json_dumps(response_payload) if response_payload is not None else None,
    )
    db.add(row)


def _state_payload(state: LicenseState) -> dict[str, Any]:
    return {
        "product_code": state.product_code,
        "installation_id": state.installation_id,
        "license_mode": state.license_mode,
        "status": state.status,
        "plan": state.plan,
        "customer_name": state.customer_name,
        "customer_email": state.customer_email,
        "valid_until": state.valid_until.isoformat() if state.valid_until else None,
        "grace_until": state.grace_until.isoformat() if state.grace_until else None,
        "last_check_at": state.last_check_at.isoformat() if state.last_check_at else None,
        "next_check_at": state.next_check_at.isoformat() if state.next_check_at else None,
        "portal_url": state.portal_url,
        "features": _parse_features(state.features_json),
        "message": state.message,
    }


def get_or_create_installation(db: Session) -> LicenseState:
    product_code = settings.esyy_product_code
    row = (
        db.query(LicenseState)
        .filter(LicenseState.product_code == product_code)
        .order_by(LicenseState.id.asc())
        .first()
    )
    if row is None:
        row = LicenseState(
            product_code=product_code,
            installation_id=str(uuid.uuid4()),
            machine_fingerprint_hash=_fingerprint_hash(),
            license_mode=_normalize_mode(settings.esyy_license_mode),
            status=LICENSE_STATUS_OPEN_TRIAL,
            plan="open_trial",
            portal_url=settings.esyy_license_portal_url or None,
            features_json=_json_dumps(_default_features()),
            message="Licenza in modalita prova gratuita aperta. Nessuna funzionalita bloccata.",
            last_check_at=None,
            next_check_at=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    changed = False
    if not (row.installation_id or "").strip():
        row.installation_id = str(uuid.uuid4())
        changed = True
    if not (row.machine_fingerprint_hash or "").strip():
        row.machine_fingerprint_hash = _fingerprint_hash()
        changed = True
    if not (row.features_json or "").strip():
        row.features_json = _json_dumps(_default_features())
        changed = True
    if changed:
        row.updated_at = _utcnow()
        db.commit()
        db.refresh(row)
    return row


def activate_open_trial(
    db: Session,
    customer_name: str | None = None,
    customer_email: str | None = None,
) -> LicenseState:
    row = get_or_create_installation(db)
    now = _utcnow()

    row.license_mode = LICENSE_MODE_OPEN_TRIAL
    row.status = LICENSE_STATUS_OPEN_TRIAL
    row.plan = "open_trial"
    row.portal_url = settings.esyy_license_portal_url or None
    row.features_json = _json_dumps(_default_features())
    row.message = "Licenza in modalita prova gratuita aperta. Nessuna funzionalita bloccata."
    if customer_name is not None:
        row.customer_name = customer_name.strip() or None
    if customer_email is not None:
        row.customer_email = customer_email.strip() or None
    row.valid_until = None
    row.grace_until = None
    row.last_check_at = now
    row.next_check_at = now + timedelta(days=1)
    row.updated_at = now

    _log_check(
        db,
        status=row.status,
        mode=row.license_mode,
        success=True,
        message=row.message,
        response_payload=_state_payload(row),
    )
    db.commit()
    db.refresh(row)
    return row


def check_license(db: Session) -> LicenseState:
    row = get_or_create_installation(db)
    now = _utcnow()
    mode = _normalize_mode(settings.esyy_license_mode)

    row.license_mode = mode
    row.portal_url = settings.esyy_license_portal_url or None
    row.features_json = _json_dumps(_default_features())
    row.last_check_at = now
    row.next_check_at = now + timedelta(days=1)

    success = True
    message = ""
    response_payload: dict[str, Any] = {}

    if mode == LICENSE_MODE_OPEN_TRIAL:
        row.status = LICENSE_STATUS_OPEN_TRIAL
        row.plan = row.plan or "open_trial"
        row.message = "Licenza in modalita prova gratuita aperta. Nessuna funzionalita bloccata."
        row.valid_until = None
        row.grace_until = None
        message = row.message
    elif mode == LICENSE_MODE_PORTAL:
        portal_url = (settings.esyy_license_portal_url or "").strip()
        if not portal_url:
            row.status = LICENSE_STATUS_PORTAL_UNREACHABLE
            row.message = (
                "Modalita portal configurata ma ESYY_LICENSE_PORTAL_URL e vuoto. "
                "Fallback locale non bloccante attivo."
            )
            success = False
        else:
            row.status = LICENSE_STATUS_WARNING
            row.message = (
                "Modalita portal impostata. Verifica remota non ancora implementata in questa build locale. "
                "Nessuna funzionalita bloccata."
            )
            success = False
        row.valid_until = None
        row.grace_until = None
        message = row.message or ""
    elif mode == LICENSE_MODE_LOCAL_FILE:
        status, local_success, local_message, payload = _license_file_status()
        row.status = status
        row.message = local_message
        success = local_success
        message = local_message
        response_payload = payload

        if payload:
            row.plan = str(payload.get("plan") or row.plan or "").strip() or None
            row.customer_name = str(payload.get("customer_name") or row.customer_name or "").strip() or None
            row.customer_email = str(payload.get("customer_email") or row.customer_email or "").strip() or None
            row.valid_until = _parse_iso_datetime(payload.get("valid_until"))
            payload_features = payload.get("features")
            if isinstance(payload_features, dict):
                merged = _default_features()
                for key, value in payload_features.items():
                    merged[str(key)] = bool(value)
                row.features_json = _json_dumps(merged)

        if row.valid_until is not None:
            row.grace_until = row.valid_until + timedelta(days=max(settings.esyy_license_grace_days, 0))
        else:
            row.grace_until = None
    else:
        row.status = LICENSE_STATUS_WARNING
        row.message = "Modalita licenza non riconosciuta. Fallback non bloccante attivo."
        success = False
        message = row.message

    row.updated_at = now
    _log_check(
        db,
        status=row.status,
        mode=row.license_mode,
        success=success,
        message=message or "",
        response_payload=response_payload or _state_payload(row),
    )
    db.commit()
    db.refresh(row)
    return row


def get_license_status(db: Session) -> dict[str, Any]:
    row = get_or_create_installation(db)
    desired_mode = _normalize_mode(settings.esyy_license_mode)
    current_status = (row.status or "").strip().lower()
    if row.license_mode != desired_mode or not current_status:
        row = check_license(db)
    elif desired_mode == LICENSE_MODE_OPEN_TRIAL and current_status != LICENSE_STATUS_OPEN_TRIAL:
        row = activate_open_trial(db, customer_name=row.customer_name, customer_email=row.customer_email)
    payload = _state_payload(row)
    payload["blocking_enabled"] = False
    payload["should_block_app"] = should_block_app(db)
    return payload


def is_feature_enabled(db: Session, feature_code: str) -> bool:
    row = get_or_create_installation(db)
    if _normalize_mode(row.license_mode) == LICENSE_MODE_OPEN_TRIAL:
        return True
    features = _parse_features(row.features_json)
    return bool(features.get(feature_code, True))


def should_block_app(db: Session) -> bool:
    _ = db
    return False


def reset_local_state(db: Session) -> LicenseState:
    row = get_or_create_installation(db)
    now = _utcnow()

    row.license_key_hash = None
    row.plan = None
    row.customer_name = None
    row.customer_email = None
    row.valid_until = None
    row.grace_until = None
    row.last_check_at = now
    row.next_check_at = now + timedelta(days=1)
    row.features_json = _json_dumps(_default_features())
    row.license_mode = _normalize_mode(settings.esyy_license_mode)
    row.status = (
        LICENSE_STATUS_OPEN_TRIAL
        if row.license_mode == LICENSE_MODE_OPEN_TRIAL
        else LICENSE_STATUS_NOT_CONFIGURED
    )
    row.message = "Stato licenza locale resettato. Nessuna funzionalita bloccata."
    row.portal_url = settings.esyy_license_portal_url or None
    row.updated_at = now

    _log_check(
        db,
        status=row.status,
        mode=row.license_mode,
        success=True,
        message=row.message,
        response_payload=_state_payload(row),
    )
    db.commit()
    db.refresh(row)
    return row
