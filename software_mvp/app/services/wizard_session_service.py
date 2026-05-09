from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import WizardSession
from .wizard_definitions import get_wizard_definition

WIZARD_STATUS_NOT_STARTED = "not_started"
WIZARD_STATUS_IN_PROGRESS = "in_progress"
WIZARD_STATUS_WAITING_EXTERNAL_ACTION = "waiting_external_action"
WIZARD_STATUS_TEST_FAILED = "test_failed"
WIZARD_STATUS_READY_TO_CONFIRM = "ready_to_confirm"
WIZARD_STATUS_COMPLETED = "completed"

WIZARD_STATUS_VALUES = {
    WIZARD_STATUS_NOT_STARTED,
    WIZARD_STATUS_IN_PROGRESS,
    WIZARD_STATUS_WAITING_EXTERNAL_ACTION,
    WIZARD_STATUS_TEST_FAILED,
    WIZARD_STATUS_READY_TO_CONFIRM,
    WIZARD_STATUS_COMPLETED,
}


def _ensure_wizard_steps(wizard_definition: dict[str, object]) -> list[dict[str, object]]:
    raw = wizard_definition.get("steps")
    if not isinstance(raw, list):
        return []
    return [step for step in raw if isinstance(step, dict)]


def _step_ids(wizard_definition: dict[str, object]) -> list[str]:
    payload: list[str] = []
    for idx, step in enumerate(_ensure_wizard_steps(wizard_definition)):
        step_id = str(step.get("id") or f"step_{idx}").strip()
        payload.append(step_id)
    return payload


def _first_step_id(wizard_definition: dict[str, object]) -> str:
    ids = _step_ids(wizard_definition)
    return ids[0] if ids else ""


def _normalize_status(status: str | None) -> str:
    clean = str(status or "").strip().lower()
    if clean in WIZARD_STATUS_VALUES:
        return clean
    return WIZARD_STATUS_IN_PROGRESS


def _load_draft_payload(raw: str | None) -> dict[str, object]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def read_draft_data(session: WizardSession) -> dict[str, object]:
    return _load_draft_payload(session.draft_data_json)


def _save_draft_payload(session: WizardSession, payload: dict[str, object]) -> None:
    session.draft_data_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _step_index_for_id(wizard_definition: dict[str, object], step_id: str | None) -> int:
    ids = _step_ids(wizard_definition)
    if not ids:
        return 0
    clean = str(step_id or "").strip()
    if not clean:
        return 0
    try:
        return ids.index(clean)
    except ValueError:
        return 0


def get_session(
    db: Session,
    tenant_id: str,
    wizard_id: str,
    user_id: int | None = None,
) -> WizardSession | None:
    query = (
        db.query(WizardSession)
        .filter(WizardSession.tenant_id == (tenant_id or "default"))
        .filter(WizardSession.wizard_id == (wizard_id or "").strip().lower())
    )
    if user_id is None:
        query = query.filter(WizardSession.user_id.is_(None))
    else:
        query = query.filter(WizardSession.user_id == user_id)
    return query.first()


def get_or_create_session(
    db: Session,
    tenant_id: str,
    wizard_id: str,
    user_id: int | None = None,
) -> WizardSession:
    tenant = (tenant_id or "default").strip() or "default"
    wizard_key = (wizard_id or "").strip().lower()

    row = get_session(db, tenant, wizard_key, user_id)
    if row is not None:
        if row.status not in WIZARD_STATUS_VALUES:
            row.status = WIZARD_STATUS_IN_PROGRESS
            row.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(row)
        return row

    definition = get_wizard_definition(wizard_key) or {}
    row = WizardSession(
        tenant_id=tenant,
        user_id=user_id,
        wizard_id=wizard_key,
        current_step_id=_first_step_id(definition),
        status=WIZARD_STATUS_NOT_STARTED,
        draft_data_json="{}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save_step_data(
    db: Session,
    session: WizardSession,
    step_id: str,
    form_data: dict[str, str],
) -> WizardSession:
    payload = read_draft_data(session)
    clean_step_id = (step_id or "").strip()
    if clean_step_id:
        payload[clean_step_id] = dict(form_data)

    _save_draft_payload(session, payload)
    session.updated_at = datetime.utcnow()
    if payload and session.status in {WIZARD_STATUS_NOT_STARTED, WIZARD_STATUS_COMPLETED}:
        session.status = WIZARD_STATUS_IN_PROGRESS
        session.completed_at = None

    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def move_to_step(db: Session, session: WizardSession, step_id: str) -> WizardSession:
    session.current_step_id = (step_id or "").strip()
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def move_next(
    db: Session,
    session: WizardSession,
    wizard_definition: dict[str, object],
) -> WizardSession:
    steps = _ensure_wizard_steps(wizard_definition)
    if not steps:
        return session

    current_index = _step_index_for_id(wizard_definition, session.current_step_id)
    target_index = min(current_index + 1, len(steps) - 1)
    target = steps[target_index]
    target_id = str(target.get("id") or f"step_{target_index}").strip()
    target_type = str(target.get("type") or "").strip().lower()

    session.current_step_id = target_id
    session.updated_at = datetime.utcnow()
    if target_type == "instruction":
        session.status = WIZARD_STATUS_WAITING_EXTERNAL_ACTION
    elif target_type == "review":
        session.status = WIZARD_STATUS_READY_TO_CONFIRM
    elif session.status != WIZARD_STATUS_TEST_FAILED:
        session.status = WIZARD_STATUS_IN_PROGRESS
    session.completed_at = None

    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def move_back(
    db: Session,
    session: WizardSession,
    wizard_definition: dict[str, object],
) -> WizardSession:
    steps = _ensure_wizard_steps(wizard_definition)
    if not steps:
        return session

    current_index = _step_index_for_id(wizard_definition, session.current_step_id)
    target_index = max(0, current_index - 1)
    target = steps[target_index]
    target_id = str(target.get("id") or f"step_{target_index}").strip()

    session.current_step_id = target_id
    session.updated_at = datetime.utcnow()
    if session.status == WIZARD_STATUS_COMPLETED:
        session.status = WIZARD_STATUS_IN_PROGRESS
        session.completed_at = None

    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def mark_completed(db: Session, session: WizardSession) -> WizardSession:
    session.status = WIZARD_STATUS_COMPLETED
    session.completed_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def set_test_result(
    db: Session,
    session: WizardSession,
    status: str,
    message: str,
) -> WizardSession:
    clean_status = _normalize_status(status)
    session.status = clean_status
    session.last_test_status = clean_status
    session.last_test_message = (message or "").strip() or None
    session.updated_at = datetime.utcnow()
    if clean_status != WIZARD_STATUS_COMPLETED:
        session.completed_at = None
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def calculate_progress(session: WizardSession, wizard_definition: dict[str, object]) -> int:
    steps = _ensure_wizard_steps(wizard_definition)
    if not steps:
        return 0
    if session.status == WIZARD_STATUS_COMPLETED:
        return 100

    payload = read_draft_data(session)
    completed = 0
    for idx, step in enumerate(steps):
        step_id = str(step.get("id") or f"step_{idx}").strip()
        raw = payload.get(step_id)
        if isinstance(raw, dict) and any(str(v).strip() for v in raw.values()):
            completed += 1

    return int((completed / len(steps)) * 100)


def required_step_missing_fields(
    session: WizardSession,
    wizard_definition: dict[str, object],
) -> list[str]:
    payload = read_draft_data(session)
    missing: list[str] = []

    for idx, step in enumerate(_ensure_wizard_steps(wizard_definition)):
        step_id = str(step.get("id") or f"step_{idx}").strip()
        step_title = str(step.get("title") or step_id)
        step_payload = payload.get(step_id)
        if not isinstance(step_payload, dict):
            step_payload = {}

        fields = step.get("fields")
        if isinstance(fields, list):
            for field in fields:
                if not isinstance(field, dict):
                    continue
                if not bool(field.get("required")):
                    continue
                field_id = str(field.get("id") or "").strip()
                if not field_id:
                    continue
                value = str(step_payload.get(field_id, "")).strip()
                if not value:
                    label = str(field.get("label") or field_id)
                    missing.append(f"{step_title}: {label}")

        step_type = str(step.get("type") or "").strip().lower()
        if step_type == "choice":
            value = str(step_payload.get("value", "")).strip()
            if not value:
                missing.append(f"{step_title}: scelta non impostata")

    return missing
