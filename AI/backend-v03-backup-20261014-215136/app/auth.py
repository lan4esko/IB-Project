"""Users, scrypt password hashing and opaque revocable sessions.

The legacy global API key cannot bypass ACL unless IB_ALLOW_LEGACY_API_KEY=true,
which is intentionally disabled by default. Pilot only; use HTTPS & throttling.
"""
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import database as dbm

LEGACY_KEY = os.getenv("IB_PLATFORM_API_KEY", "")
ALLOW_LEGACY = os.getenv("IB_ALLOW_LEGACY_API_KEY", "false").lower() == "true"
TOKEN_HOURS = 8


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("Длина пароля должна быть 12–128 символов")
    salt = secrets.token_bytes(16)
    result = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${result.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, digest = encoded.split("$")
        if algorithm != "scrypt" or (int(n), int(r), int(p)) != (16384, 8, 1):
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt),
                                n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class Actor:
    id: int | None
    username: str
    role: str
    session_id: int | None = None


def actor_dependency(authorization: str | None = Header(default=None),
                     x_api_key: str | None = Header(default=None),
                     db: Session = Depends(dbm.get_db)) -> Actor:
    if ALLOW_LEGACY and LEGACY_KEY and x_api_key and hmac.compare_digest(LEGACY_KEY, x_api_key):
        return Actor(None, "legacy-service-key", "admin")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Требуется Authorization: Bearer <token>",
                            headers={"WWW-Authenticate": "Bearer"})
    token = authorization[7:].strip()
    if len(token) < 32 or len(token) > 256:
        raise HTTPException(401, "Недействительная сессия")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = db.scalar(select(dbm.UserSession).where(dbm.UserSession.token_hash == digest))
    if session is None or session.revoked_at is not None:
        raise HTTPException(401, "Недействительная сессия")
    expiration = session.expires_at
    if expiration.tzinfo is None:
        expiration = expiration.replace(tzinfo=timezone.utc)
    if expiration <= datetime.now(timezone.utc):
        raise HTTPException(401, "Сессия истекла")
    user = db.get(dbm.User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Пользователь отключён")
    return Actor(user.id, user.username, user.role, session.id)


def require_roles(actor: Actor, *roles: str) -> None:
    if actor.role not in roles:
        raise HTTPException(403, "Недостаточно прав")


def may_access_object(db: Session, actor: Actor, object_id: int, write: bool = False) -> bool:
    if actor.role == "admin":
        return True
    if actor.id is None:
        return False
    grant = db.scalar(select(dbm.ObjectGrant).where(
        dbm.ObjectGrant.object_id == object_id, dbm.ObjectGrant.user_id == actor.id))
    return grant is not None and (grant.permission == "write" or not write)


def new_session(db: Session, user: dbm.User) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(48)
    expiry = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    db.add(dbm.UserSession(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                           expires_at=expiry))
    db.commit()
    return token, expiry
