from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import AppUser

ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
VALID_ROLES = {ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER}

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 390000


@dataclass
class AuthResult:
    ok: bool
    message: str
    user: AppUser | None = None


def normalize_role(role: str) -> str:
    role_clean = (role or "").strip().lower()
    if role_clean not in VALID_ROLES:
        return ROLE_VIEWER
    return role_clean


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password vuota non consentita")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iterations_str, salt_hex, digest_hex = stored_hash.split("$", 3)
        algorithm = algo.replace("pbkdf2_", "")
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except Exception:  # noqa: BLE001
        return False

    candidate = hashlib.pbkdf2_hmac(
        algorithm,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(candidate, expected)


def authenticate_user(db: Session, username: str, password: str) -> AuthResult:
    user = (
        db.query(AppUser)
        .filter(AppUser.username == username.strip().lower())
        .first()
    )
    if not user:
        return AuthResult(ok=False, message="Utente non trovato.")
    if not user.is_active:
        return AuthResult(ok=False, message="Utente disattivato.")
    if not verify_password(password, user.password_hash):
        return AuthResult(ok=False, message="Password non valida.")
    return AuthResult(ok=True, message="Autenticazione riuscita.", user=user)


def ensure_default_admin(db: Session, username: str, password: str) -> AppUser | None:
    user_count = db.query(AppUser).count()
    if user_count > 0:
        return None

    username_clean = username.strip().lower()
    if not username_clean:
        username_clean = "admin"
    if not password:
        password = "admin123!"

    user = AppUser(
        username=username_clean,
        password_hash=hash_password(password),
        role=ROLE_ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def upsert_user(
    db: Session,
    username: str,
    role: str,
    is_active: bool,
    password: str | None = None,
) -> AppUser:
    username_clean = username.strip().lower()
    row = db.query(AppUser).filter(AppUser.username == username_clean).first()
    if row is None:
        if not password:
            raise ValueError("Password obbligatoria per nuovo utente")
        row = AppUser(
            username=username_clean,
            password_hash=hash_password(password),
            role=normalize_role(role),
            is_active=is_active,
        )
        db.add(row)
    else:
        row.role = normalize_role(role)
        row.is_active = is_active
        if password:
            row.password_hash = hash_password(password)
    db.commit()
    db.refresh(row)
    return row
