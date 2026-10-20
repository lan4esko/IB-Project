"""OI Registry v0.7.0 — consolidated registry, reviews and configurable queries."""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import uuid
from contextvars import ContextVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from zipfile import ZipFile, BadZipFile

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, cast, func, or_, select, Text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.inspection import inspect

from app.db import get_db
from app.models import (
    User, Session as LoginSession, InformationObject, Asset,
    FieldDefinition, FieldValue, FieldValueRevision, FieldAssertionRevision, Document,
    FieldEvidence, AuditEvent, ConfigurationBaseline, ConfigurationChange,
    AssetComponent, SharedPeripheral, AssetPeripheralAccess, AssetSecurityTool,
    ServiceRequest, WorkEntry, AssetInspection, OIReview, OIReviewFinding, AssetMNI, AssetZMNI, ZMNIContainerHistory, OIProposal, PlannedActivity, ControlRule, TransferApproval, SystemType, RegistryRequest, now,
)

app = FastAPI(title="OI Registry", version="0.7.0-rc1", docs_url=None, redoc_url=None)
AUDIT_REQUEST = ContextVar('oi_audit_request', default={})
try:
    LOCAL_TIMEZONE = ZoneInfo(os.getenv('OI_REPORT_TZ', 'Europe/Moscow'))
except ZoneInfoNotFoundError:
    # Debian slim images without system tzdata should not prevent API startup.
    LOCAL_TIMEZONE = timezone(timedelta(hours=3))

@app.middleware('http')
async def attach_request_context(request: Request, call_next):
    request_id = str(uuid.uuid4())
    token = AUDIT_REQUEST.set({
        'request_id': request_id,
        'source_ip': request.client.host if request.client else '',
        'user_agent': request.headers.get('User-Agent', '')[:256],
    })
    try:
        response = await call_next(request)
        response.headers['X-Request-ID'] = request_id
        return response
    finally:
        AUDIT_REQUEST.reset(token)

PASSWORD_HASHER = PasswordHasher()
SESSION_SECRET = os.environ.get("OI_SESSION_SECRET", "test-only-session-secret")
SECURE_COOKIE = os.environ.get("OI_COOKIE_SECURE", "false").lower() == "true"
DOCUMENT_ROOT = Path(os.environ.get("OI_DOCUMENT_ROOT", "/tmp/oi-registry-docs"))
MAX_FILE_SIZE = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt", ".md", ".csv"}
OI_COLUMNS = ("code", "name", "classification", "location", "status", "attestation_issued_on", "attestation_valid_until", "attestation_document_id", "attestation_smb_path", "attestation_notice_days", "openproject_project_id", "notes")
ASSET_COLUMNS = ("code", "oi_id", "serial_number", "inventory_number", "device_type", "model", "os_name", "os_version", "network_segment", "ip_address", "hostname", "domain_name", "seal_state", "status", "notes")
ALL_EXPORT_COLUMNS = ("code", "oi_code", "serial_number", "inventory_number", "device_type", "model", "os_name", "os_version", "network_segment", "ip_address", "hostname", "domain_name", "seal_state", "status", "notes")

class Credentials(BaseModel):
    username: str
    password: str

class OIInput(BaseModel):
    code: str = Field(min_length=1,max_length=80)
    name: str = Field(min_length=1,max_length=250)
    classification: str = Field(default='',max_length=250)
    location: str = Field(default='',max_length=250)
    status: str = Field(default='formation',max_length=40)
    attestation_issued_on: date | None = None
    attestation_valid_until: date | None = None
    attestation_document_id: int | None = Field(default=None,ge=1)  # compatibility only
    attestation_smb_path: str = Field(default="", max_length=2048)
    attestation_notice_days: int = Field(default=90,ge=1,le=730)
    openproject_project_id: int | None = Field(default=None,ge=1)
    notes: str = Field(default='',max_length=10000)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

class OIPatch(BaseModel):
    code: str | None = Field(default=None,min_length=1,max_length=80)
    name: str | None = Field(default=None,min_length=1,max_length=250)
    classification: str | None = Field(default=None,max_length=250)
    location: str | None = Field(default=None,max_length=250)
    status: str | None = Field(default=None,max_length=40)
    attestation_issued_on: date | None = None
    attestation_valid_until: date | None = None
    attestation_document_id: int | None = Field(default=None,ge=1)  # compatibility only
    attestation_smb_path: str | None = Field(default=None, max_length=2048)
    attestation_notice_days: int | None = Field(default=None,ge=1,le=730)
    openproject_project_id: int | None = Field(default=None,ge=1)
    notes: str | None = Field(default=None,max_length=10000)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

class AssetInput(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    oi_id: int | None = Field(default=None, ge=1)
    serial_number: str = Field(default="", max_length=150)
    inventory_number: str = Field(default="", max_length=150)
    device_type: str = Field(default="", max_length=100)
    model: str = Field(default="", max_length=200)
    os_name: str = Field(default="", max_length=150)
    os_version: str = Field(default="", max_length=100)
    network_segment: str = Field(default="", max_length=150)
    ip_address: str = Field(default="", max_length=60)
    hostname: str = Field(default="", max_length=250)
    domain_name: str = Field(default="", max_length=250)
    seal_state: Literal["unknown", "sealed", "opened", "unsealed_after_repair", "seal_damaged", "not_applicable"] = "unknown"
    status: str = Field(default="operational", max_length=40)
    notes: str = Field(default="", max_length=10000)
    savz_name: str = Field(default='', max_length=200)
    savz_version: str = Field(default='', max_length=120)
    szi_nsd_name: str = Field(default='', max_length=200)
    szi_nsd_version: str = Field(default='', max_length=120)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

class AssetPatch(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    oi_id: int | None = Field(default=None, ge=1)
    serial_number: str | None = Field(default=None, max_length=150)
    inventory_number: str | None = Field(default=None, max_length=150)
    device_type: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=200)
    os_name: str | None = Field(default=None, max_length=150)
    os_version: str | None = Field(default=None, max_length=100)
    network_segment: str | None = Field(default=None, max_length=150)
    ip_address: str | None = Field(default=None, max_length=60)
    hostname: str | None = Field(default=None, max_length=250)
    domain_name: str | None = Field(default=None, max_length=250)
    seal_state: Literal["unknown", "sealed", "opened", "unsealed_after_repair", "seal_damaged", "not_applicable"] | None = None
    status: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=10000)
    savz_name: str | None = Field(default=None, max_length=200)
    savz_version: str | None = Field(default=None, max_length=120)
    szi_nsd_name: str | None = Field(default=None, max_length=200)
    szi_nsd_version: str | None = Field(default=None, max_length=120)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

class FieldCreate(BaseModel):
    entity_type: Literal["oi", "asset", "request"]
    scope_entity_id: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=150)
    field_type: Literal["text", "number", "date", "boolean", "select"] = "text"
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=100)

class FieldPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    required: bool | None = None
    active: bool | None = None
    options: list[str] | None = None

class ValueInput(BaseModel):
    value: Any

class EvidenceInput(BaseModel):
    entity_type: Literal["oi", "asset"]
    entity_id: int = Field(ge=1)
    field_key: str = Field(min_length=1, max_length=80)
    document_id: int = Field(ge=1)
    kind: Literal["evidence", "regulation"] = "evidence"
    locator_type: Literal["page", "section", "cell", "text"]
    locator_value: str = Field(min_length=1, max_length=150)
    comment: str = Field(default="", max_length=500)


def asdict(item):
    return {c.key: getattr(item, c.key) for c in inspect(item).mapper.column_attrs}

def audit_asdict(db: DBSession, event: AuditEvent):
    data=asdict(event)
    account=db.get(User,event.actor_id)
    data['actor_username']=account.username if account else '<unknown>'
    data['actor_display_name']=account.display_name if account else ''
    return data


def audit(db: DBSession, user: User, action: str, entity_type: str, entity_id: int, details=None):
    context = AUDIT_REQUEST.get()
    db.add(AuditEvent(actor_id=user.id, action=action, entity_type=entity_type,
                      entity_id=entity_id, details=details or {},
                      request_id=context.get('request_id',''),
                      source_ip=context.get('source_ip',''),
                      user_agent=context.get('user_agent','')))


def token_digest(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token: str):
    return hmac.new(SESSION_SECRET.encode(), ("csrf:" + token).encode(), hashlib.sha256).hexdigest()


def current_user(request: Request, db: DBSession = Depends(get_db)) -> User:
    token = request.cookies.get("oi_session", "")
    if not token:
        raise HTTPException(401, "Выполните вход")
    login = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_digest(token)))
    if not login:
        raise HTTPException(401, "Сеанс не найден")
    expires = login.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        raise HTTPException(401, "Сеанс истёк")
    user = db.get(User, login.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Учётная запись неактивна")
    if user.must_change_password and request.url.path not in {
        '/api/auth/me', '/api/auth/password', '/api/auth/logout'}:
        raise HTTPException(403, 'Сначала смените первоначальный пароль')
    if user.role == 'requester' and request.url.path not in {
        '/api/auth/me', '/api/auth/password', '/api/auth/logout'} and not request.url.path.startswith('/api/proposals'):
        raise HTTPException(403, 'Ответственному за ОИ доступна только подача заявок')
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        provided = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(token_digest(provided), login.csrf_hash):
            raise HTTPException(403, "CSRF-токен не совпадает")
    return user


def editor_or_admin(user: User = Depends(current_user)):
    if user.role not in ('admin', 'editor'):
        raise HTTPException(403, 'Требуется оператор БД или администратор')
    return user


def admin_only(user: User = Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Требуются права администратора")
    return user


def entity(db: DBSession, entity_type: str, entity_id: int):
    model = {"oi": InformationObject, "asset": Asset, "request": RegistryRequest}.get(entity_type)
    if not model:
        raise HTTPException(422, "Неизвестный тип сущности")
    record = db.get(model, entity_id)
    if not record:
        raise HTTPException(404, "Карточка не найдена")
    return record


def field_current_value(db: DBSession, entity_type: str, entity_id: int, field_key: str):
    record = entity(db, entity_type, entity_id)
    columns = OI_COLUMNS if entity_type == "oi" else ASSET_COLUMNS
    if field_key in columns:
        return getattr(record, field_key)
    if field_key.startswith("custom:"):
        try:
            f_id = int(field_key.split(":", 1)[1])
        except ValueError:
            raise HTTPException(422, "Неверный идентификатор поля")
        definition = db.get(FieldDefinition, f_id)
        if not definition or definition.entity_type != entity_type or (definition.scope_entity_id is not None and definition.scope_entity_id != entity_id):
            raise HTTPException(404, "Поле не найдено")
        field = db.scalar(select(FieldValue).where(FieldValue.field_id == f_id,
                         FieldValue.entity_type == entity_type, FieldValue.entity_id == entity_id))
        return field.value if field else None
    raise HTTPException(422, "Недопустимое поле")


def value_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()

def latest_revision(db: DBSession, entity_type: str, entity_id: int, field_key: str):
    return db.scalar(select(FieldAssertionRevision).where(
        FieldAssertionRevision.entity_type == entity_type,
        FieldAssertionRevision.entity_id == entity_id,
        FieldAssertionRevision.field_key == field_key).order_by(FieldAssertionRevision.id.desc()).limit(1))


def new_revision(db: DBSession, user: User, entity_type: str, entity_id: int, field_key: str, value):
    revision = FieldAssertionRevision(entity_type=entity_type, entity_id=entity_id, field_key=field_key,
                                      value_hash=value_digest(value), changed_by=user.id)
    db.add(revision)
    db.flush()
    return revision


def commit(db: DBSession):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Запись с таким идентификатором или названием уже существует")


def require_oi(db, oi_id):
    if not db.get(InformationObject, oi_id):
        raise HTTPException(422, "Указанный ОИ не найден")


def validate_field(definition: FieldDefinition, value):
    kind = definition.field_type
    if value is None or value == "":
        if definition.required:
            raise HTTPException(422, "Обязательное поле не может быть пустым")
        return None
    if kind == "text":
        if not isinstance(value, str) or len(value) > 10000:
            raise HTTPException(422, "Ожидается текст до 10 000 символов")
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HTTPException(422, "Ожидается число")
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise HTTPException(422, "Ожидается да/нет")
    elif kind == "date":
        if not isinstance(value, str):
            raise HTTPException(422, "Ожидается дата YYYY-MM-DD")
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(422, "Неверная дата")
    elif kind == "select":
        if value not in definition.options:
            raise HTTPException(422, "Значение отсутствует в разрешённом списке")
    return value



def normalize_custom_fields(db: DBSession, entity_type: str, submitted: dict, *, entity_id: int | None = None, creating: bool = False):
    """Validate admin-defined fields before changing system rows; no client-supplied names/SQL."""
    if len(submitted) > 200:
        raise HTTPException(422, 'Слишком много пользовательских полей')
    definitions = list(db.scalars(select(FieldDefinition).where(
        FieldDefinition.entity_type == entity_type, FieldDefinition.active.is_(True),
        or_(FieldDefinition.scope_entity_id.is_(None), FieldDefinition.scope_entity_id == entity_id)
        if entity_id is not None else FieldDefinition.scope_entity_id.is_(None))))
    by_id = {str(item.id): item for item in definitions}
    values = {}
    for key, value in submitted.items():
        definition = by_id.get(str(key))
        if definition is None:
            raise HTTPException(422, 'Пользовательское поле не существует или недоступно: ' + str(key))
        try:
            values[definition.id] = validate_field(definition, value)
        except HTTPException as exc:
            raise HTTPException(exc.status_code, f'{definition.name}: {exc.detail}') from exc
    if creating:
        absent = [d.name for d in definitions if d.required and (d.id not in values or values[d.id] is None)]
        if absent:
            raise HTTPException(422, 'Заполните обязательные поля: ' + ', '.join(absent))
    return values


def store_custom_fields(db: DBSession, user: User, entity_type: str, entity_id: int, values: dict[int, Any]):
    for field_id, value in values.items():
        rec = db.scalar(select(FieldValue).where(FieldValue.entity_type == entity_type,
            FieldValue.entity_id == entity_id, FieldValue.field_id == field_id))
        old = rec.value if rec else None
        normalized_text = str(value).casefold() if value is not None else ''
        if rec is None:
            db.add(FieldValue(entity_type=entity_type, entity_id=entity_id,
                field_id=field_id, value=value, value_text=normalized_text, updated_by=user.id))
        else:
            rec.value = value
            rec.value_text = normalized_text
            rec.updated_by = user.id
        db.add(FieldValueRevision(entity_type=entity_type, entity_id=entity_id,
            field_id=field_id, value=value, updated_by=user.id))
        if old != value:
            new_revision(db, user, entity_type, entity_id, f'custom:{field_id}', value)
    if values:
        audit(db, user, 'set_custom_fields', entity_type, entity_id,
              {'field_ids': sorted(values), 'count': len(values)})

def asset_filters(q="", oi_id=None, status="", network_segment="", os_name="", field_id=None, field_value=""):
    conditions = []
    if q:
        t = f"%{q.strip()}%"
        conditions.append(or_(*[getattr(Asset, name).ilike(t) for name in
                                ("code", "serial_number", "inventory_number", "model", "os_name", "os_version", "network_segment", "ip_address", "hostname", "domain_name", "seal_state", "notes")],
                              InformationObject.code.ilike(t), InformationObject.name.ilike(t),
                              Asset.id.in_(select(AssetComponent.asset_id).where(
                                  or_(AssetComponent.serial_number.ilike(t),
                                      AssetComponent.model.ilike(t)))),
                              Asset.id.in_(select(AssetPeripheralAccess.asset_id).join(
                                  SharedPeripheral, SharedPeripheral.id == AssetPeripheralAccess.peripheral_id).where(
                                  SharedPeripheral.serial_number.ilike(t),
                                  AssetPeripheralAccess.revoked_at.is_(None)))))
    if oi_id is not None:
        conditions.append(Asset.oi_id == oi_id)
    if status:
        conditions.append(Asset.status == status)
    if network_segment:
        conditions.append(Asset.network_segment == network_segment)
    if os_name:
        conditions.append(Asset.os_name.ilike(f"%{os_name}%"))
    return conditions


def assets_query(q="", oi_id=None, status="", network_segment="", os_name="", field_id=None, field_value=""):
    stmt = select(Asset, InformationObject.code.label("oi_code")).join(
        InformationObject, InformationObject.id == Asset.oi_id, isouter=True)
    for c in asset_filters(q, oi_id, status, network_segment, os_name, field_id, field_value):
        stmt = stmt.where(c)
    if field_id is not None:
        stmt = stmt.join(FieldValue, and_(FieldValue.entity_type == "asset", FieldValue.entity_id == Asset.id,
                                         FieldValue.field_id == field_id))
        if field_value:
            stmt = stmt.where(FieldValue.value_text.contains(field_value.casefold()))
    return stmt.order_by(Asset.id)


@app.get("/api/health/live")
def live():
    return {"status": "ok", "version": "0.7.0-rc1"}


@app.get("/api/health/ready")
def ready(db: DBSession = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ready", "database": "postgresql"}


@app.post("/api/auth/login")
def login(data: Credentials, response: Response, db: DBSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username, User.active.is_(True)))
    try:
        valid = user is not None and PASSWORD_HASHER.verify(user.password_hash, data.password)
    except (VerifyMismatchError, VerificationError):
        valid = False
    if not valid:
        raise HTTPException(401, "Неверный логин или пароль")
    token = secrets.token_urlsafe(40)
    csrf = csrf_token(token)
    expiry = now() + timedelta(hours=12)
    db.add(LoginSession(user_id=user.id, token_hash=token_digest(token), csrf_hash=token_digest(csrf), expires_at=expiry))
    audit(db, user, 'login', 'user', user.id)
    commit(db)
    response.set_cookie("oi_session", token, max_age=43200, httponly=True, secure=SECURE_COOKIE, samesite="strict", path="/")
    return {"id": user.id, "username": user.username, "role": user.role, "must_change_password": user.must_change_password, "csrf": csrf}


@app.get("/api/auth/me")
def me(request: Request, user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username, "role": user.role, "must_change_password": user.must_change_password, "csrf": csrf_token(request.cookies["oi_session"])}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    record = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_digest(request.cookies["oi_session"])))
    if record:
        db.delete(record)
        commit(db)
    response.delete_cookie("oi_session", path="/")
    return {"ok": True}


@app.get("/api/dashboard")
def dashboard(db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    return {
        "objects": db.scalar(select(func.count()).select_from(InformationObject)),
        "assets": db.scalar(select(func.count()).select_from(Asset)),
        "documents": db.scalar(select(func.count()).select_from(Document)),
        "custom_fields": db.scalar(select(func.count()).select_from(FieldDefinition).where(FieldDefinition.active.is_(True))),
        "latest_changes": [audit_asdict(db,e) for e in db.scalars((select(AuditEvent) if user.role=="admin" else select(AuditEvent).where(AuditEvent.actor_id==user.id)).order_by(AuditEvent.id.desc()).limit(10))],
    }


@app.get("/api/objects")
def list_objects(q: str = "", db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(InformationObject).order_by(InformationObject.code)
    if q:
        stmt = stmt.where(or_(InformationObject.code.ilike(f"%{q}%"), InformationObject.name.ilike(f"%{q}%")))
    return [asdict(x) for x in db.scalars(stmt.limit(2000))]


# v0.6: every OI import must be previewed and reconfirmed before it can write business data.
@app.get('/api/objects/{oi_id}/transfer.zip')
def object_transfer_export(oi_id: int, db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    from app.object_transfer import export_oi
    bundle = export_oi(db, oi_id)
    audit(db, user, 'oi_transfer_export', 'oi', oi_id, {'size': len(bundle)})
    commit(db)
    return Response(bundle, media_type='application/zip', headers={
        'Content-Disposition': f'attachment; filename="oi-{oi_id}-emergency.zip"',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@app.post('/api/objects/transfer/preview')
async def object_transfer_preview(file: UploadFile = File(...),
                                  mode: Literal['merge', 'copy', 'replace'] = Form(...),
                                  db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    from app.object_transfer import parse_bundle, inventory, digest, diff, CONFIRMATION_TTL, MAX_ARCHIVE
    raw = await file.read(MAX_ARCHIVE + 1)
    payload = parse_bundle(raw)
    nonce = str(uuid.uuid4())
    comparisons = {candidate: diff(db, payload, candidate, nonce.replace('-', ''))
                   for candidate in ('merge', 'copy', 'replace')}
    changes = comparisons[mode]
    phrase = 'ПОДТВЕРЖДАЮ ' + secrets.token_hex(4).upper()
    baseline = digest(inventory(db, payload['object']['code']))
    record = TransferApproval(id=nonce, actor_id=user.id, object_code=payload['object']['code'],
                              mode=mode, archive_digest=hashlib.sha256(raw).hexdigest(),
                              baseline_digest=baseline, confirm_digest=token_digest(phrase),
                              expires_at=datetime.now(timezone.utc) + CONFIRMATION_TTL)
    db.add(record)
    commit(db)
    return {'plan_id': record.id, 'expires_at': record.expires_at.isoformat(), 'confirmation_phrase': phrase,
            'preview': changes, 'comparisons': comparisons, 'options': [
                {'mode': 'merge', 'description': 'Добавить новые записи, конфликты блокируют импорт'},
                {'mode': 'copy', 'description': 'Создать отдельный ОИ и новые коды СВТ'},
                {'mode': 'replace', 'description': 'Заменить паспорта; отсутствующие СВТ вывести из эксплуатации, историю сохранить'}]}


@app.post('/api/objects/transfer/commit')
async def object_transfer_commit(plan_id: str = Form(...), mode: Literal['merge', 'copy', 'replace'] = Form(...),
                                 confirmation_phrase: str = Form(...), file: UploadFile = File(...),
                                 db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    from app.object_transfer import parse_bundle, inventory, digest, diff, apply, MAX_ARCHIVE
    raw = await file.read(MAX_ARCHIVE + 1)
    payload = parse_bundle(raw)
    # Lock the approval row. A replay or parallel confirmation cannot spend it twice on PostgreSQL.
    record = db.scalar(select(TransferApproval).where(TransferApproval.id == plan_id).with_for_update())
    if not record or record.actor_id != user.id:
        raise HTTPException(404, 'Подготовленная операция не найдена')
    expiry = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)
    if record.used_at is not None or expiry <= datetime.now(timezone.utc):
        raise HTTPException(409, 'Подтверждение уже использовано или просрочено. Создайте новый предпросмотр.')
    if record.mode != mode or record.object_code != payload['object']['code'] or not hmac.compare_digest(record.archive_digest, hashlib.sha256(raw).hexdigest()):
        raise HTTPException(409, 'Режим или содержимое архива изменились. Создайте новый предпросмотр.')
    if not hmac.compare_digest(record.confirm_digest, token_digest(confirmation_phrase)):
        raise HTTPException(403, 'Не получено повторное подтверждение операции')
    # Lock current OI/asset rows while comparing with the preview and applying changes.
    locked = db.scalar(select(InformationObject).where(
        InformationObject.code == record.object_code).with_for_update())
    if locked is not None:
        list(db.scalars(select(Asset).where(Asset.oi_id == locked.id).with_for_update()))
    if record.baseline_digest != digest(inventory(db, record.object_code)):
        raise HTTPException(409, 'С момента предпросмотра данные ОИ изменились. Проверьте изменения заново.')
    changes = diff(db, payload, mode, record.id.replace('-', ''))
    if not changes['can_apply']:
        raise HTTPException(409, {'message': 'Обнаружены конфликты. Импорт не выполнен.', 'conflicts': changes['conflicts']})
    obj = apply(db, payload, mode, record.id.replace('-', ''), user.id)
    db.flush()
    record.used_at = datetime.now(timezone.utc)
    audit(db, user, 'oi_transfer_commit', 'oi', obj.id, {
        'mode': mode, 'plan_id': record.id, 'archive_sha256': record.archive_digest,
        'object_code': obj.code, 'added_assets': changes['add_assets'],
        'changed_assets': changes['change_assets'], 'retired_assets': changes['retire_missing_assets']})
    commit(db)
    return {'ok': True, 'object_id': obj.id, 'object_code': obj.code, 'mode': mode,
            'message': 'Импорт завершён. История ремонтов и документы не импортировались.'}


@app.get("/api/objects/{id}")
def get_object(id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    return asdict(entity(db, "oi", id))


@app.post("/api/objects", status_code=201)
def create_object(data: OIInput, db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    if data.attestation_issued_on and data.attestation_valid_until and data.attestation_valid_until < data.attestation_issued_on:
        raise HTTPException(422, 'Контрольная дата не может предшествовать дате аттестации')
    if data.attestation_document_id:
        check_document(db, data.attestation_document_id)
    custom = normalize_custom_fields(db, "oi", data.custom_fields, creating=True)
    record = InformationObject(**data.model_dump(exclude={"custom_fields"}))
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Код ОИ уже существует")
    store_custom_fields(db, user, "oi", record.id, custom)
    audit(db, user, "create", "oi", record.id, {"values": data.model_dump(mode="json")})
    commit(db)
    return asdict(record)


@app.patch("/api/objects/{id}")
def update_object(id: int, data: OIPatch, db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    record = entity(db, "oi", id)
    changes = data.model_dump(exclude_unset=True)
    raw_custom = changes.pop("custom_fields", {})
    custom = normalize_custom_fields(db, "oi", raw_custom, entity_id=id)
    if changes.get('attestation_document_id'):
        check_document(db, changes['attestation_document_id'])
    issued = changes.get('attestation_issued_on', record.attestation_issued_on)
    valid = changes.get('attestation_valid_until', record.attestation_valid_until)
    if issued and valid and valid < issued:
        raise HTTPException(422, 'Контрольная дата не может предшествовать дате аттестации')
    before = {k: getattr(record, k) for k in changes}
    for k, v in changes.items():
        setattr(record, k, v)
        if before[k] != v:
            new_revision(db, user, "oi", id, k, v)
    store_custom_fields(db, user, "oi", id, custom)
    audit(db, user, "update", "oi", id, {"before": {k:(v.isoformat() if isinstance(v,date) else v) for k,v in before.items()}, "after": {k:(v.isoformat() if isinstance(v,date) else v) for k,v in changes.items()}})
    commit(db)
    return asdict(record)


@app.get("/api/assets")
def list_assets(q: str = "", oi_id: int | None = None, status: str = "", network_segment: str = "", os_name: str = "",
                field_id: int | None = None, field_value: str = "", limit: int = Query(100, ge=1, le=1000),
                offset: int = Query(0, ge=0), db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    stmt = assets_query(q, oi_id, status, network_segment, os_name, field_id, field_value)
    count = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    records = db.execute(stmt.limit(limit).offset(offset)).all()
    return {"total": count, "items": [{**asdict(a), "oi_code": code} for a, code in records]}


@app.get("/api/assets/export.csv")
def export_assets(q: str = "", oi_id: int | None = None, status: str = "", network_segment: str = "", os_name: str = "",
                  field_id: int | None = None, field_value: str = "", columns: str = "",
                  db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    requested = [c.strip() for c in columns.split(",") if c.strip()] if columns else list(ALL_EXPORT_COLUMNS)
    valid_custom = {f"custom:{x.id}": x.name for x in db.scalars(select(FieldDefinition).where(FieldDefinition.entity_type == "asset"))}
    if not requested or len(requested) > 45 or any(c not in ALL_EXPORT_COLUMNS and c not in valid_custom for c in requested):
        raise HTTPException(422, "Недопустимые колонки выгрузки")
    rows = db.execute(assets_query(q, oi_id, status, network_segment, os_name, field_id, field_value).limit(20001)).all()
    if len(rows) > 20000:
        raise HTTPException(413, "Слишком много строк; уточните фильтр")
    ids = [a.id for a, _ in rows]
    value_map = {}
    if ids:
        for v in db.scalars(select(FieldValue).where(FieldValue.entity_type == "asset", FieldValue.entity_id.in_(ids))):
            value_map[(v.entity_id, f"custom:{v.field_id}")] = v.value
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";")
    writer.writerow([valid_custom.get(k, k) for k in requested])
    for a, code in rows:
        d = {**asdict(a), "oi_code": code}
        values = []
        for k in requested:
            val = value_map.get((a.id, k), "") if k.startswith("custom:") else d.get(k, "")
            if val is None:
                val = ""
            if isinstance(val, (list, dict)):
                val = json.dumps(val, ensure_ascii=False)
            text = str(val)
            if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                text = "'" + text  # prevent Excel/LibreOffice formula injection
            values.append(text)
        writer.writerow(values)
    audit(db, user, "export_csv", "asset", 0, {"count": len(rows), "columns": requested})
    commit(db)
    raw = "\ufeff" + stream.getvalue()
    return Response(raw, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="oi-assets.csv"', "Cache-Control": "no-store"})


@app.get("/api/assets/{id}")
def get_asset(id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    return asdict(entity(db, "asset", id))


@app.post("/api/assets", status_code=201)
def create_asset(data: AssetInput, db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    if data.oi_id is not None:
        require_oi(db, data.oi_id)
    custom = normalize_custom_fields(db, "asset", data.custom_fields, creating=True)
    record = Asset(**data.model_dump(exclude={"custom_fields"}))
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Код СВТ уже существует")
    store_custom_fields(db, user, "asset", record.id, custom)
    audit(db, user, "create", "asset", record.id, {"values": data.model_dump(mode="json")})
    commit(db)
    return asdict(record)


@app.patch("/api/assets/{id}")
def update_asset(id: int, data: AssetPatch, db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    record = entity(db, "asset", id)
    changes = data.model_dump(exclude_unset=True)
    raw_custom = changes.pop("custom_fields", {})
    custom = normalize_custom_fields(db, "asset", raw_custom, entity_id=id)
    if "oi_id" in changes:
        if changes["oi_id"] is not None:
            require_oi(db, changes["oi_id"])
    before = {k: getattr(record, k) for k in changes}
    for k, v in changes.items():
        setattr(record, k, v)
        if before[k] != v:
            new_revision(db, user, "asset", id, k, v)
    store_custom_fields(db, user, "asset", id, custom)
    audit(db, user, "update", "asset", id, {"before": before, "after": changes})
    commit(db)
    return asdict(record)


@app.get("/api/fields")
def list_fields(entity_type: Literal["oi", "asset", "request"], entity_id: int | None = None, all_scopes: bool = False,
                db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(FieldDefinition).where(FieldDefinition.entity_type == entity_type)
    if not all_scopes:
        stmt = stmt.where(or_(FieldDefinition.scope_entity_id.is_(None), FieldDefinition.scope_entity_id == entity_id)) if entity_id is not None else stmt.where(FieldDefinition.scope_entity_id.is_(None))
    return [asdict(f) for f in db.scalars(stmt.order_by(FieldDefinition.id))]


@app.post("/api/fields", status_code=201)
def create_field(data: FieldCreate, db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    if data.field_type == "select" and not data.options:
        raise HTTPException(422, "Заполните варианты списка")
    if data.scope_entity_id is not None:
        entity(db, data.entity_type, data.scope_entity_id)
    duplicates = db.scalar(select(FieldDefinition).where(FieldDefinition.entity_type == data.entity_type,
                           FieldDefinition.scope_entity_id == data.scope_entity_id, FieldDefinition.name == data.name))
    if duplicates:
        raise HTTPException(409, "Поле с таким названием уже существует в этой области")
    record = FieldDefinition(**data.model_dump())
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Поле с таким названием уже существует")
    audit(db, user, "create_field", data.entity_type, 0, {"field_id": record.id, "name": record.name})
    commit(db)
    return asdict(record)


@app.patch("/api/fields/{id}")
def update_field(id: int, data: FieldPatch, db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    record = db.get(FieldDefinition, id)
    if not record:
        raise HTTPException(404, "Поле не найдено")
    changes = data.model_dump(exclude_unset=True)
    if "options" in changes and record.field_type != "select":
        raise HTTPException(422, "Списки значений доступны только для типа select")
    for k, v in changes.items():
        setattr(record, k, v)
    audit(db, user, "update_field", record.entity_type, 0, {"field_id": id, "changes": changes})
    commit(db)
    return asdict(record)


@app.get("/api/values/{entity_type}/{entity_id}")
def list_values(entity_type: Literal["oi", "asset", "request"], entity_id: int,
                db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    entity(db, entity_type, entity_id)
    result = db.execute(select(FieldValue, FieldDefinition).join(FieldDefinition, FieldDefinition.id == FieldValue.field_id).where(
        FieldValue.entity_type == entity_type, FieldValue.entity_id == entity_id)).all()
    return [{"field_id": defn.id, "name": defn.name, "type": defn.field_type, "value": val.value,
             "updated_at": val.updated_at} for val, defn in result]


@app.put("/api/values/{entity_type}/{entity_id}/{field_id}")
def put_value(entity_type: Literal["oi", "asset", "request"], entity_id: int, field_id: int, data: ValueInput,
              db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    entity(db, entity_type, entity_id)
    definition = db.get(FieldDefinition, field_id)
    if not definition or definition.entity_type != entity_type or not definition.active or (definition.scope_entity_id is not None and definition.scope_entity_id != entity_id):
        raise HTTPException(404, "Активное поле не найдено")
    value = validate_field(definition, data.value)
    record = db.scalar(select(FieldValue).where(FieldValue.entity_type == entity_type,
                   FieldValue.entity_id == entity_id, FieldValue.field_id == field_id))
    old = record.value if record else None
    if record:
        record.value = value
        record.value_text = str(value).casefold() if value is not None else ""
        record.updated_by = user.id
    else:
        db.add(FieldValue(entity_type=entity_type, entity_id=entity_id, field_id=field_id, value=value, value_text=str(value).casefold() if value is not None else "", updated_by=user.id))
    db.add(FieldValueRevision(entity_type=entity_type, entity_id=entity_id, field_id=field_id, value=value, updated_by=user.id))
    if old != value:
        new_revision(db, user, entity_type, entity_id, f"custom:{field_id}", value)
    audit(db, user, "set_value", entity_type, entity_id, {"field_id": field_id, "before": old, "after": value})
    commit(db)
    return {"field_id": field_id, "value": value}


@app.get("/api/values/{entity_type}/{entity_id}/{field_id}/history")
def value_history(entity_type: Literal["oi", "asset", "request"], entity_id: int, field_id: int,
                  db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    entity(db, entity_type, entity_id)
    return [asdict(v) for v in db.scalars(select(FieldValueRevision).where(
        FieldValueRevision.entity_type == entity_type, FieldValueRevision.entity_id == entity_id,
        FieldValueRevision.field_id == field_id).order_by(FieldValueRevision.id.desc()).limit(100))]


def valid_file_type(file_name: str, content: bytes):
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Разрешены PDF, DOCX, XLSX, TXT, MD, CSV")
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(415, "Неверная сигнатура PDF")
    if extension in {".docx", ".xlsx"}:
        if not content.startswith(b"PK"):
            raise HTTPException(415, "Неверная сигнатура Office-файла")
        try:
            with ZipFile(io.BytesIO(content)) as z:
                names = z.namelist()
                if "[Content_Types].xml" not in names or not any(n.startswith("word/") if extension == ".docx" else n.startswith("xl/") for n in names):
                    raise HTTPException(415, "Неверная структура Office-файла")
        except BadZipFile:
            raise HTTPException(415, "Повреждён Office-файл")
    return extension


@app.post("/api/documents", status_code=201)
async def upload_document(title: str, file: UploadFile = File(...), db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    filename = Path(file.filename or "").name
    if not filename or len(filename) > 255 or len(title) > 250 or not title.strip():
        raise HTTPException(422, "Укажите название документа и имя файла")
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Документ превышает 25 МБ")
    extension = valid_file_type(filename, content)
    key = secrets.token_hex(24)
    DOCUMENT_ROOT.mkdir(parents=True, exist_ok=True)
    path = DOCUMENT_ROOT / key
    path.write_bytes(content)
    try:
        record = Document(title=title.strip(), original_filename=filename,
                          storage_key=key, content_type={".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/plain", ".csv": "text/csv"}.get(extension, "application/octet-stream"),
                          sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content), created_by=user.id)
        db.add(record)
        db.flush()
        audit(db, user, "upload", "document", record.id, {"title": title, "sha256": record.sha256})
        commit(db)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return asdict(record)


@app.get("/api/documents")
def list_documents(q: str = "", db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Document).order_by(Document.id.desc()).limit(1000)
    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%"))
    return [asdict(d) for d in db.scalars(stmt)]


@app.get("/api/documents/{id}/file")
def fetch_document(id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    document = db.get(Document, id)
    if not document:
        raise HTTPException(404, "Документ не найден")
    path = DOCUMENT_ROOT / document.storage_key
    if not path.is_file():
        raise HTTPException(404, "Файл документа отсутствует")
    if hashlib.sha256(path.read_bytes()).hexdigest() != document.sha256:
        raise HTTPException(409, "Контрольная сумма файла не совпадает")
    return FileResponse(path, media_type=document.content_type, filename=document.original_filename,
                        content_disposition_type="inline" if document.content_type == "application/pdf" else "attachment",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                                 "Content-Security-Policy": "sandbox"})


@app.post("/api/evidence", status_code=201)
def create_evidence(data: EvidenceInput, db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    val = field_current_value(db, data.entity_type, data.entity_id, data.field_key)
    if not db.get(Document, data.document_id):
        raise HTTPException(404, "Документ не найден")
    if data.locator_type == "page" and (not data.locator_value.isdigit() or int(data.locator_value) < 1):
        raise HTTPException(422, "Страница должна быть положительным числом")
    bound = latest_revision(db, data.entity_type, data.entity_id, data.field_key)
    if bound is None or bound.value_hash != value_digest(val):
        bound = new_revision(db, user, data.entity_type, data.entity_id, data.field_key, val)
    record = FieldEvidence(**data.model_dump(), value_hash=value_digest(val),
                           value_revision_id=bound.id, created_by=user.id)
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Основание уже существует")
    audit(db, user, "add_evidence", data.entity_type, data.entity_id,
          {"field_key": data.field_key, "document_id": data.document_id, "locator": data.locator_value})
    commit(db)
    return asdict(record)


@app.get("/api/evidence/{entity_type}/{entity_id}")
def list_evidence(entity_type: Literal["oi", "asset"], entity_id: int, field_key: str = "",
                  db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    entity(db, entity_type, entity_id)
    stmt = select(FieldEvidence, Document.title).join(Document, FieldEvidence.document_id == Document.id).where(
        FieldEvidence.entity_type == entity_type, FieldEvidence.entity_id == entity_id).order_by(FieldEvidence.id.desc())
    if field_key:
        stmt = stmt.where(FieldEvidence.field_key == field_key)
    result = []
    for ev, title in db.execute(stmt).all():
        try:
            version = latest_revision(db, entity_type, entity_id, ev.field_key)
            current = (version is not None and version.id == ev.value_revision_id and
                       value_digest(field_current_value(db, entity_type, entity_id, ev.field_key)) == ev.value_hash)
        except HTTPException:
            current = False
        result.append({**asdict(ev), "document_title": title, "current_value": current,
                       "file_url": f"/api/documents/{ev.document_id}/file" +
                                   (f"#page={ev.locator_value}" if ev.locator_type == "page" else "")})
    return result


@app.get("/api/audit")
def list_audit(entity_type: str = "", entity_id: int | None = None, limit: int = Query(100, ge=1, le=500),
               db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    if user.role != 'admin':
        raise HTTPException(403, 'Журнал действий доступен главному администратору')
    return [audit_asdict(db,x) for x in db.scalars(stmt)]


# ---- OI Registry v0.2: immutable attested-composition candidates ----

BASELINE_ASSET_KEYS = (
    "code", "serial_number", "inventory_number", "device_type", "model",
    "os_name", "os_version", "network_segment", "ip_address", "hostname", "domain_name", "seal_state", "status", "notes"
)
BASELINE_OI_KEYS = ("code", "name", "classification", "location", "notes", "attestation_issued_on", "attestation_valid_until")
CHANGE_TYPES = ("replacement", "repair", "software", "network", "addition", "removal", "other")
CHANGE_STATUSES = ("proposed", "under_review", "approved", "implemented", "rejected", "cancelled")
CHANGE_TRANSITIONS = {
    "proposed": {"under_review", "cancelled"},
    "under_review": {"approved", "rejected", "cancelled"},
    "approved": {"implemented", "cancelled"},
    "implemented": set(), "rejected": set(), "cancelled": set(),
}


class BaselineCreate(BaseModel):
    version: str = Field(min_length=1, max_length=80, pattern=r"^[\w.\-]+$")
    notes: str = Field(min_length=5, max_length=4000)
    document_id: int | None = Field(default=None, ge=1)


class BaselineApprove(BaseModel):
    confirmation: bool
    document_id: int = Field(ge=1)
    approval_note: str = Field(min_length=10, max_length=4000)


class ChangeCreate(BaseModel):
    asset_id: int | None = Field(default=None, ge=1)
    change_type: Literal["replacement", "repair", "software", "network", "addition", "removal", "other"]
    summary: str = Field(min_length=5, max_length=350)
    justification: str = Field(min_length=5, max_length=4000)
    document_id: int | None = Field(default=None, ge=1)
    openproject_work_package_id: int | None = Field(default=None, ge=1)


class ChangeUpdate(BaseModel):
    status: Literal["under_review", "approved", "implemented", "rejected", "cancelled"]
    resolution: str = Field(min_length=10, max_length=4000)
    document_id: int | None = Field(default=None, ge=1)
    openproject_work_package_id: int | None = Field(default=None, ge=1)



# Physical MNI and encrypted ZMNI are independent from the asset lifecycle entries.
class MNIInput(BaseModel):
    serial_number: str = Field(min_length=1, max_length=150)
    accounting_number: str = Field(min_length=1, max_length=150)
    media_type: str = Field(default='', max_length=60)

class ZMNIInput(BaseModel):
    serial_number: str = Field(min_length=1, max_length=150)
    accounting_number: str = Field(min_length=1, max_length=150)
    software_version: str = Field(default='', max_length=120)
    container_filename: str = Field(default='', max_length=255)
    container_issued_on: date | None = None

class ZMNIContainerUpdate(BaseModel):
    container_filename: str = Field(min_length=1, max_length=255)
    container_issued_on: date

@app.get('/api/assets/{asset_id}/mni')
def get_asset_mni(asset_id: int, db: DBSession=Depends(get_db), user: User=Depends(current_user)):
    require_asset(db,asset_id)
    return [asdict(x) for x in db.scalars(select(AssetMNI).where(AssetMNI.asset_id==asset_id).order_by(AssetMNI.id))]

@app.post('/api/assets/{asset_id}/mni',status_code=201)
def add_asset_mni(asset_id: int,data: MNIInput,db:DBSession=Depends(get_db),user:User=Depends(editor_or_admin)):
    require_asset(db,asset_id)
    obj=AssetMNI(asset_id=asset_id,**data.model_dump())
    db.add(obj)
    try: db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'МНИ с таким заводским номером уже учтён на СВТ')
    audit(db,user,'asset_mni_created','mni',obj.id,{'asset_id':asset_id,'serial_number':obj.serial_number,'accounting_number':obj.accounting_number})
    commit(db)
    return asdict(obj)

@app.get('/api/assets/{asset_id}/zmni')
def get_asset_zmni(asset_id: int,db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    require_asset(db,asset_id)
    return [asdict(x) for x in db.scalars(select(AssetZMNI).where(AssetZMNI.asset_id==asset_id).order_by(AssetZMNI.id))]

@app.post('/api/assets/{asset_id}/zmni',status_code=201)
def add_asset_zmni(asset_id: int,data: ZMNIInput,db:DBSession=Depends(get_db),user:User=Depends(editor_or_admin)):
    require_asset(db,asset_id)
    obj=AssetZMNI(asset_id=asset_id,**data.model_dump())
    db.add(obj)
    try: db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'ЗМНИ с таким заводским номером уже учтён на СВТ')
    if obj.container_filename and obj.container_issued_on:
        db.add(ZMNIContainerHistory(zmni_id=obj.id,container_filename=obj.container_filename,
            container_issued_on=obj.container_issued_on,recorded_by=user.id))
    audit(db,user,'asset_zmni_created','zmni',obj.id,{'asset_id':asset_id,'serial_number':obj.serial_number,'accounting_number':obj.accounting_number})
    commit(db)
    return asdict(obj)

@app.post('/api/assets/{asset_id}/zmni/{zmni_id}/container')
def renew_zmni_container(asset_id:int,zmni_id:int,data:ZMNIContainerUpdate,
                         db:DBSession=Depends(get_db),user:User=Depends(editor_or_admin)):
    require_asset(db,asset_id)
    obj=db.get(AssetZMNI,zmni_id)
    if obj is None or obj.asset_id!=asset_id:
        raise HTTPException(404,'ЗМНИ не найден на этой СВТ')
    if obj.container_issued_on and data.container_issued_on < obj.container_issued_on:
        raise HTTPException(422,'Дата нового контейнера не должна быть раньше действующего')
    previous={'container_filename':obj.container_filename,'container_issued_on':str(obj.container_issued_on)}
    obj.container_filename=data.container_filename
    obj.container_issued_on=data.container_issued_on
    db.add(ZMNIContainerHistory(zmni_id=obj.id,container_filename=data.container_filename,
                                container_issued_on=data.container_issued_on,recorded_by=user.id))
    audit(db,user,'zmni_container_reissued','zmni',obj.id,{'before':previous,'after':data.model_dump(mode='json')})
    commit(db)
    return asdict(obj)

class MediaIdentityPatch(BaseModel):
    serial_number: str = Field(min_length=1, max_length=150)
    accounting_number: str = Field(min_length=1, max_length=150)
    media_type: str = Field(default='', max_length=60)

class ZMNIIdentityPatch(BaseModel):
    serial_number: str = Field(min_length=1, max_length=150)
    accounting_number: str = Field(min_length=1, max_length=150)
    software_version: str = Field(default='', max_length=120)

@app.patch('/api/assets/{asset_id}/mni/{mni_id}')
def update_asset_mni(asset_id:int,mni_id:int,data:MediaIdentityPatch,
                     db:DBSession=Depends(get_db),user:User=Depends(editor_or_admin)):
    require_asset(db,asset_id)
    item=db.get(AssetMNI,mni_id)
    if not item or item.asset_id!=asset_id:raise HTTPException(404,'МНИ не найден на этой СВТ')
    before={key:getattr(item,key) for key in data.model_fields}
    for key,value in data.model_dump().items():setattr(item,key,value)
    audit(db,user,'asset_mni_corrected','mni',item.id,{'before':before,'after':data.model_dump()})
    commit(db)
    return asdict(item)

@app.patch('/api/assets/{asset_id}/zmni/{zmni_id}')
def update_asset_zmni(asset_id:int,zmni_id:int,data:ZMNIIdentityPatch,
                      db:DBSession=Depends(get_db),user:User=Depends(editor_or_admin)):
    require_asset(db,asset_id)
    item=db.get(AssetZMNI,zmni_id)
    if not item or item.asset_id!=asset_id:raise HTTPException(404,'ЗМНИ не найден на этой СВТ')
    before={key:getattr(item,key) for key in data.model_fields}
    for key,value in data.model_dump().items():setattr(item,key,value)
    audit(db,user,'asset_zmni_corrected','zmni',item.id,{'before':before,'after':data.model_dump()})
    commit(db)
    return asdict(item)

@app.get('/api/assets/{asset_id}/zmni/{zmni_id}/history')
def get_zmni_history(asset_id:int,zmni_id:int,db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    require_asset(db,asset_id)
    obj=db.get(AssetZMNI,zmni_id)
    if obj is None or obj.asset_id!=asset_id: raise HTTPException(404,'ЗМНИ не найден на этой СВТ')
    return [asdict(x) for x in db.scalars(select(ZMNIContainerHistory).where(
        ZMNIContainerHistory.zmni_id==zmni_id).order_by(ZMNIContainerHistory.id))]

# OI review findings are deliberately separate from quarterly per-SVT inspections.
class OIReviewInput(BaseModel):
    reviewed_on: date
    reviewer: str = Field(min_length=2, max_length=180)
    report_smb_path: str = Field(default='', max_length=2048)
    notes: str = Field(default='', max_length=10000)

    @field_validator('report_smb_path')
    @classmethod
    def valid_report_path(cls, value):
        if value and not (value.startswith('\\\\') or value.lower().startswith('smb://')):
            raise ValueError('Укажите путь \\\\server\\share\\report.pdf или smb://server/share/report.pdf')
        return value

class OIFindingInput(BaseModel):
    category: Literal['deficiency', 'violation']
    description: str = Field(min_length=2, max_length=10000)
    corrective_action: str = Field(default='', max_length=10000)

class OIFindingResolution(BaseModel):
    resolved: bool
    corrective_action: str = Field(default='', max_length=10000)


@app.get('/api/objects/{oi_id}/reviews')
def list_oi_reviews(oi_id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    entity(db, 'oi', oi_id)
    reviews = list(db.scalars(select(OIReview).where(OIReview.oi_id == oi_id).order_by(OIReview.reviewed_on.desc(), OIReview.id.desc())))
    ids = [r.id for r in reviews]
    findings = {i: [] for i in ids}
    if ids:
        for item in db.scalars(select(OIReviewFinding).where(OIReviewFinding.review_id.in_(ids)).order_by(OIReviewFinding.id)):
            findings[item.review_id].append(asdict(item))
    return [{**asdict(r), 'findings': findings[r.id],
             'open_count': sum(not f['resolved'] for f in findings[r.id])} for r in reviews]


@app.post('/api/objects/{oi_id}/reviews', status_code=201)
def create_oi_review(oi_id: int, data: OIReviewInput, db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    entity(db, 'oi', oi_id)
    review = OIReview(oi_id=oi_id, **data.model_dump(), created_by=user.id)
    db.add(review); db.flush()
    audit(db, user, 'oi_review_created', 'oi_review', review.id,
          {'oi_id': oi_id, 'reviewed_on': data.reviewed_on.isoformat(), 'report_smb_path': data.report_smb_path})
    commit(db)
    return asdict(review)


def review_for_object(db: DBSession, oi_id: int, review_id: int):
    entity(db, 'oi', oi_id)
    review = db.get(OIReview, review_id)
    if review is None or review.oi_id != oi_id:
        raise HTTPException(404, 'Проверка этого ОИ не найдена')
    return review


@app.post('/api/objects/{oi_id}/reviews/{review_id}/findings', status_code=201)
def create_oi_finding(oi_id: int, review_id: int, data: OIFindingInput,
                      db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    review_for_object(db, oi_id, review_id)
    finding = OIReviewFinding(review_id=review_id, **data.model_dump(), created_by=user.id)
    db.add(finding); db.flush()
    audit(db, user, 'oi_finding_created', 'oi_finding', finding.id, {'oi_id': oi_id, 'review_id': review_id, **data.model_dump()})
    commit(db)
    return asdict(finding)


@app.patch('/api/objects/{oi_id}/reviews/{review_id}/findings/{finding_id}')
def resolve_oi_finding(oi_id: int, review_id: int, finding_id: int, data: OIFindingResolution,
                       db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    review_for_object(db, oi_id, review_id)
    finding = db.get(OIReviewFinding, finding_id)
    if finding is None or finding.review_id != review_id:
        raise HTTPException(404, 'Замечание не относится к указанной проверке')
    previous = {'resolved': finding.resolved, 'corrective_action': finding.corrective_action}
    finding.resolved = data.resolved
    finding.corrective_action = data.corrective_action
    finding.resolved_by = user.id if data.resolved else None
    finding.resolved_at = now() if data.resolved else None
    audit(db, user, 'oi_finding_resolution', 'oi_finding', finding.id,
          {'oi_id': oi_id, 'review_id': review_id, 'before': previous,
           'after': {'resolved': data.resolved, 'corrective_action': data.corrective_action}})
    commit(db)
    return asdict(finding)

def check_document(db: DBSession, document_id: int | None):
    if document_id is not None and db.get(Document, document_id) is None:
        raise HTTPException(422, "Указанный документ отсутствует")


def configuration_snapshot(db: DBSession, oi_id: int):
    oi = db.get(InformationObject, oi_id)
    if oi is None:
        raise HTTPException(404, "ОИ не найден")
    assets = list(db.scalars(select(Asset).where(Asset.oi_id == oi_id).order_by(Asset.id)))
    ids = [x.id for x in assets]
    custom = list(db.scalars(select(FieldValue).where(
        or_(and_(FieldValue.entity_type == "oi", FieldValue.entity_id == oi_id),
            and_(FieldValue.entity_type == "asset", FieldValue.entity_id.in_(ids))
            if ids else False))))
    definitions = {x.id: x.name for x in db.scalars(select(FieldDefinition))}

    def fields(kind, record_id):
        return {str(f.field_id): {"name": definitions.get(f.field_id, str(f.field_id)), "value": f.value}
                for f in custom if f.entity_type == kind and f.entity_id == record_id}

    def asset_inventory(asset_id):
        components = list(db.scalars(select(AssetComponent).where(
            AssetComponent.asset_id == asset_id, AssetComponent.removed_at.is_(None)).order_by(AssetComponent.id)))
        security = list(db.scalars(select(AssetSecurityTool).where(
            AssetSecurityTool.asset_id == asset_id, AssetSecurityTool.removed_at.is_(None)).order_by(AssetSecurityTool.id)))
        access = list(db.scalars(select(AssetPeripheralAccess).where(
            AssetPeripheralAccess.asset_id == asset_id, AssetPeripheralAccess.revoked_at.is_(None)).order_by(AssetPeripheralAccess.id)))
        peripherals = [db.get(SharedPeripheral, link.peripheral_id) for link in access]
        return {
            "components": [{"id": c.id, "kind": c.kind, "serial_number": c.serial_number,
                            "model": c.model, "manufacturer": c.manufacturer,
                            "inventory_number": c.inventory_number} for c in components],
            "security_tools": [{"id": t.id, "name": t.name, "version": t.version,
                                "license_ref": t.license_ref, "expires_on": t.expires_on} for t in security],
            "peripherals": [{"id": d.id, "name": d.name, "serial_number": d.serial_number,
                             "kind": d.kind, "ip_address": d.ip_address, "manufacturer":d.manufacturer, "model":d.model, "inventory_number":d.inventory_number, "media_present":d.media_present, "media_serial_number":d.media_serial_number} for d in peripherals if d],
        }
    return {
        "oi": {**{k: (getattr(oi,k).isoformat() if isinstance(getattr(oi,k), date) else getattr(oi,k)) for k in BASELINE_OI_KEYS}, "fields": fields("oi", oi_id)},
        "assets": [{"id": x.id, **{k: getattr(x, k) for k in BASELINE_ASSET_KEYS},
                    "fields": fields("asset", x.id), **asset_inventory(x.id)} for x in assets],
    }


def snapshot_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def differences(snapshot, current):
    result = {"oi_fields": [], "added": [], "removed": [], "modified": []}
    previous_oi, present_oi = snapshot["oi"], current["oi"]
    for key in sorted(set(previous_oi) | set(present_oi)):
        if previous_oi.get(key) != present_oi.get(key):
            result["oi_fields"].append({"field": key, "before": previous_oi.get(key), "after": present_oi.get(key)})
    old = {x["id"]: x for x in snapshot["assets"]}
    new = {x["id"]: x for x in current["assets"]}
    for id in sorted(set(new) - set(old)):
        result["added"].append(new[id])
    for id in sorted(set(old) - set(new)):
        result["removed"].append(old[id])
    for id in sorted(set(old) & set(new)):
        changes = [{"field": key, "before": old[id].get(key), "after": new[id].get(key)}
                   for key in sorted(set(old[id]) | set(new[id]))
                   if key != "id" and old[id].get(key) != new[id].get(key)]
        if changes:
            result["modified"].append({"asset_id": id, "code_before": old[id].get("code"),
                                       "code_after": new[id].get("code"), "fields": changes})
    return result


def baseline_for_oi(db: DBSession, oi_id: int, baseline_id: int):
    item = db.get(ConfigurationBaseline, baseline_id)
    if item is None or item.oi_id != oi_id:
        raise HTTPException(404, "Снимок этого ОИ не найден")
    return item


@app.get("/api/objects/{oi_id}/baselines")
def list_baselines(oi_id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    entity(db, "oi", oi_id)
    return [{k: v for k, v in asdict(x).items() if k != "snapshot"}
            for x in db.scalars(select(ConfigurationBaseline).where(
                ConfigurationBaseline.oi_id == oi_id).order_by(ConfigurationBaseline.id.desc()))]


@app.post("/api/objects/{oi_id}/baselines", status_code=201)
def create_baseline(oi_id: int, data: BaselineCreate,
                    db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    entity(db, "oi", oi_id)
    check_document(db, data.document_id)
    snap = configuration_snapshot(db, oi_id)
    record = ConfigurationBaseline(oi_id=oi_id, version=data.version, notes=data.notes,
                                   document_id=data.document_id, snapshot=snap,
                                   snapshot_sha256=snapshot_hash(snap), created_by=user.id)
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Такая версия комплекта у этого ОИ уже есть")
    audit(db, user, "create_baseline", "oi", oi_id, {"baseline_id": record.id, "version": data.version,
                                                     "snapshot_sha256": record.snapshot_sha256})
    commit(db)
    return {k: v for k, v in asdict(record).items() if k != "snapshot"}


@app.get("/api/objects/{oi_id}/baselines/{baseline_id}")
def get_baseline(oi_id: int, baseline_id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    return asdict(baseline_for_oi(db, oi_id, baseline_id))


@app.post("/api/objects/{oi_id}/baselines/{baseline_id}/approve")
def approve_baseline(oi_id: int, baseline_id: int, data: BaselineApprove,
                     db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    record = baseline_for_oi(db, oi_id, baseline_id)
    if record.status != "draft":
        raise HTTPException(409, "Утверждать можно только черновик")
    if not data.confirmation:
        raise HTTPException(422, "Требуется явное подтверждение проверки документов")
    check_document(db, data.document_id)
    current = configuration_snapshot(db, oi_id)
    if snapshot_hash(current) != record.snapshot_sha256:
        raise HTTPException(409, "Фактический состав изменился после создания черновика; создайте новый снимок")
    record.status = "approved"
    record.document_id = data.document_id
    record.approval_note = data.approval_note
    record.approved_by = user.id
    record.approved_at = now()
    audit(db, user, "approve_baseline", "oi", oi_id,
          {"baseline_id": baseline_id, "document_id": data.document_id})
    commit(db)
    return {k: v for k, v in asdict(record).items() if k != "snapshot"}


@app.get("/api/objects/{oi_id}/configuration/compare")
def compare_configuration(oi_id: int, baseline_id: int | None = None,
                          db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    entity(db, "oi", oi_id)
    if baseline_id is None:
        record = db.scalar(select(ConfigurationBaseline).where(
            ConfigurationBaseline.oi_id == oi_id,
            ConfigurationBaseline.status == "approved").order_by(ConfigurationBaseline.id.desc()).limit(1))
        if record is None:
            raise HTTPException(404, "Нет утверждённого снимка; выберите черновик по baseline_id")
    else:
        record = baseline_for_oi(db, oi_id, baseline_id)
    current = configuration_snapshot(db, oi_id)
    delta = differences(record.snapshot, current)
    mismatch = any(delta[k] for k in delta)
    return {"oi_id": oi_id, "baseline_id": record.id, "baseline_version": record.version,
            "baseline_status": record.status, "snapshot_sha256": record.snapshot_sha256,
            "matches": not mismatch, "changes": delta, "current_assets": len(current["assets"]),
            "baseline_assets": len(record.snapshot["assets"])}


@app.get("/api/objects/{oi_id}/changes")
def list_changes(oi_id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    entity(db, "oi", oi_id)
    return [asdict(x) for x in db.scalars(select(ConfigurationChange).where(
        ConfigurationChange.oi_id == oi_id).order_by(ConfigurationChange.id.desc()))]


@app.post("/api/objects/{oi_id}/changes", status_code=201)
def create_change(oi_id: int, data: ChangeCreate,
                  db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    entity(db, "oi", oi_id)
    if data.asset_id is not None:
        asset = db.get(Asset, data.asset_id)
        if not asset or asset.oi_id != oi_id:
            raise HTTPException(422, "СВТ отсутствует в данном ОИ")
    check_document(db, data.document_id)
    record = ConfigurationChange(oi_id=oi_id, created_by=user.id, **data.model_dump())
    db.add(record)
    db.flush()
    audit(db, user, "create_change", "oi", oi_id, {"change_id": record.id, "summary": data.summary})
    commit(db)
    return asdict(record)


@app.patch("/api/objects/{oi_id}/changes/{change_id}")
def update_change(oi_id: int, change_id: int, data: ChangeUpdate,
                  db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    entity(db, "oi", oi_id)
    record = db.get(ConfigurationChange, change_id)
    if not record or record.oi_id != oi_id:
        raise HTTPException(404, "Заявка этого ОИ не найдена")
    if data.status not in CHANGE_TRANSITIONS[record.status]:
        raise HTTPException(409, "Переход состояния заявки запрещён")
    if data.document_id is not None:
        check_document(db, data.document_id)
        record.document_id = data.document_id
    if data.openproject_work_package_id is not None:
        record.openproject_work_package_id = data.openproject_work_package_id
    old_status = record.status
    record.status = data.status
    record.resolution = data.resolution
    record.updated_by = user.id
    record.updated_at = now()
    audit(db, user, "update_change", "oi", oi_id,
          {"change_id": change_id, "before": old_status, "after": data.status})
    commit(db)
    return asdict(record)

# ---- Asset electronic logbook: components, MFP permissions, services and inspections ----

COMPONENT_KINDS = {"system_unit", "disk", "keyboard", "mouse", "power_supply", "monitor", "printer", "other"}
SEAL_STATES = {"unknown", "sealed", "opened", "unsealed_after_repair", "seal_damaged", "not_applicable"}
INSPECTION_CATEGORIES = {
    "unauthorized_software", "unauthorized_files", "removable_media", "access_violation",
    "policy_violation", "malware_indicators", "physical_security", "other"
}
INSPECTION_CHECKS = {"unauthorized_content", "installed_software", "removable_media", "access_controls", "antivirus", "seals"}


class ComponentCreate(BaseModel):
    kind: Literal["system_unit", "disk", "keyboard", "mouse", "power_supply", "monitor", "printer", "other"]
    manufacturer: str = Field(default="", max_length=150)
    model: str = Field(default="", max_length=200)
    serial_number: str = Field(min_length=1, max_length=150)
    inventory_number: str = Field(default="", max_length=150)
    document_id: int | None = Field(default=None, ge=1)


class RetireInput(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


class PeripheralCreate(BaseModel):
    kind: Literal["mfp", "printer", "scanner", "other"] = "mfp"
    name: str = Field(min_length=3, max_length=250)
    serial_number: str = Field(min_length=1, max_length=150)
    ip_address: str = Field(default="", max_length=60)
    manufacturer: str = Field(default="", max_length=150)
    model: str = Field(default="", max_length=200)
    inventory_number: str = Field(default="", max_length=150)
    media_present: bool = False
    media_kind: str = Field(default="", max_length=100)
    media_serial_number: str = Field(default="", max_length=150)
    media_inventory_number: str = Field(default="", max_length=150)


class PeripheralPatch(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=250)
    serial_number: str | None = Field(default=None, min_length=1, max_length=150)
    ip_address: str | None = Field(default=None, max_length=60)
    manufacturer: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=200)
    inventory_number: str | None = Field(default=None, max_length=150)
    media_present: bool | None = None
    media_kind: str | None = Field(default=None, max_length=100)
    media_serial_number: str | None = Field(default=None, max_length=150)
    media_inventory_number: str | None = Field(default=None, max_length=150)


class PeripheralGrant(BaseModel):
    peripheral_id: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=2000)
    connection_type: Literal['usb','lan','print_server','other'] = 'lan'
    driver_name: str = Field(default='', max_length=250)
    driver_version: str = Field(default='', max_length=120)
    driver_smb_path: str = Field(default='', max_length=700)
    driver_sha256: str = Field(default='', max_length=64)
    driver_document_id: int | None = Field(default=None, ge=1)

    @field_validator('driver_smb_path')
    @classmethod
    def validate_smb_path(cls, value):
        if not value:
            return value
        if not (value.startswith('smb://') or value.startswith('\\\\')) or '@' in value or '..' in value:
            raise ValueError('Укажите путь smb://server/share/файл или UNC без учётных данных и ..')
        return value

    @field_validator('driver_sha256')
    @classmethod
    def validate_sha256(cls, value):
        if value and (len(value)!=64 or any(c not in '0123456789abcdefABCDEF' for c in value)):
            raise ValueError('SHA-256 должен содержать 64 шестнадцатеричных символа')
        return value


class SecurityToolCreate(BaseModel):
    name: str = Field(min_length=2, max_length=250)
    version: str = Field(default="", max_length=120)
    license_ref: str = Field(default="", max_length=150)
    expires_on: str = Field(default="", pattern=r"^$|^\d{4}-\d{2}-\d{2}$")
    document_id: int | None = Field(default=None, ge=1)


class ServiceRequestCreate(BaseModel):
    reporter: str = Field(min_length=2, max_length=180)
    reported_at: datetime | None = None
    subject: str = Field(min_length=5, max_length=350)
    fault_description: str = Field(min_length=5, max_length=8000)
    document_id: int | None = Field(default=None, ge=1)
    openproject_work_package_id: int | None = Field(default=None, ge=1)


class ServiceRequestClose(BaseModel):
    resolution: str = Field(min_length=10, max_length=4000)


class WorkEntryCreate(BaseModel):
    service_request_id: int | None = Field(default=None, ge=1)
    performed_at: datetime | None = None
    performer: str = Field(min_length=2, max_length=180)
    work_type: Literal["diagnostics", "repair", "replacement", "configuration", "preventive", "other"]
    actions: str = Field(min_length=5, max_length=8000)
    result: str = Field(min_length=5, max_length=8000)
    seal_state_after: Literal["unknown", "sealed", "opened", "unsealed_after_repair", "seal_damaged", "not_applicable"]
    seal_note: str = Field(default="", max_length=2000)
    document_page: int | None = Field(default=None, ge=1)
    document_id: int | None = Field(default=None, ge=1)


class InspectionCreate(BaseModel):
    inspected_at: datetime | None = None
    inspector: str = Field(min_length=2, max_length=180)
    subject_user: str = Field(default="", max_length=180)
    checklist: dict[str, Literal["ok", "violation", "not_applicable", "not_checked"]]
    violation_categories: list[str] = Field(default_factory=list, max_length=30)
    finding_summary: str = Field(min_length=5, max_length=8000)
    corrective_action: str = Field(default="", max_length=8000)
    document_page: int | None = Field(default=None, ge=1)
    status: Literal["passed", "violations", "review_required"]
    document_id: int | None = Field(default=None, ge=1)


def require_asset(db, asset_id):
    return entity(db, "asset", asset_id)


def require_record(db, model, record_id, asset_id):
    item = db.get(model, record_id)
    if item is None or item.asset_id != asset_id:
        raise HTTPException(404, "Запись для данной СВТ не найдена")
    return item


def safe_event_time(value):
    value = value or now()
    if value.tzinfo is None:
        raise HTTPException(422, "Укажите дату и время с часовым поясом")
    if value > now() + timedelta(minutes=5):
        raise HTTPException(422, "Дата не должна находиться в будущем")
    return value.astimezone(timezone.utc)


@app.get("/api/assets/{asset_id}/components")
def list_components(asset_id: int, current_only: bool = False,
                    db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    require_asset(db, asset_id)
    query = select(AssetComponent).where(AssetComponent.asset_id == asset_id)
    if current_only:
        query = query.where(AssetComponent.removed_at.is_(None))
    return [asdict(x) for x in db.scalars(query.order_by(AssetComponent.id))]


@app.post("/api/assets/{asset_id}/components", status_code=201)
def add_component(asset_id: int, data: ComponentCreate, db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    require_asset(db, asset_id)
    check_document(db, data.document_id)
    item = AssetComponent(asset_id=asset_id, created_by=user.id, **data.model_dump())
    db.add(item)
    db.flush()
    audit(db, user, "component_installed", "asset", asset_id, {"component_id": item.id, "serial_number": item.serial_number})
    commit(db)
    return asdict(item)


@app.post("/api/assets/{asset_id}/components/{component_id}/remove")
def remove_component(asset_id: int, component_id: int, data: RetireInput,
                     db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    require_asset(db, asset_id)
    item = require_record(db, AssetComponent, component_id, asset_id)
    if item.removed_at:
        raise HTTPException(409, "Комплектующее уже выведено из состава")
    item.removed_at, item.removal_reason = now(), data.reason
    audit(db, user, "component_removed", "asset", asset_id, {"component_id": item.id, "reason": data.reason})
    commit(db)
    return asdict(item)


@app.get("/api/objects/{oi_id}/peripherals")
def list_peripherals(oi_id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    entity(db, "oi", oi_id)
    return [asdict(x) for x in db.scalars(select(SharedPeripheral).where(SharedPeripheral.oi_id == oi_id).order_by(SharedPeripheral.id))]


@app.post("/api/objects/{oi_id}/peripherals", status_code=201)
def add_peripheral(oi_id: int, data: PeripheralCreate, db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    entity(db, "oi", oi_id)
    item = SharedPeripheral(oi_id=oi_id, created_by=user.id, **data.model_dump())
    db.add(item)
    db.flush()
    audit(db, user, "peripheral_registered", "oi", oi_id, {"peripheral_id": item.id, "values":data.model_dump(mode="json")})
    commit(db)
    return asdict(item)


@app.patch('/api/objects/{oi_id}/peripherals/{peripheral_id}')
def update_peripheral(oi_id:int,peripheral_id:int,data:PeripheralPatch,
                      db:DBSession=Depends(get_db),user:User=Depends(editor_or_admin)):
    entity(db,'oi',oi_id)
    peripheral=db.get(SharedPeripheral,peripheral_id)
    if not peripheral or peripheral.oi_id!=oi_id:
        raise HTTPException(404,'МФУ не найдено в составе ОИ')
    changes=data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422,'Нет данных для изменения')
    before={key:getattr(peripheral,key) for key in changes}
    for key,value in changes.items():setattr(peripheral,key,value)
    audit(db,user,'peripheral_updated','oi',oi_id,{'peripheral_id':peripheral_id,'before':before,'after':changes})
    commit(db)
    return asdict(peripheral)


@app.get("/api/assets/{asset_id}/peripherals")
def asset_peripherals(asset_id: int, current_only: bool = False,
                      db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    require_asset(db, asset_id)
    q = select(AssetPeripheralAccess).where(AssetPeripheralAccess.asset_id == asset_id)
    if current_only:
        q = q.where(AssetPeripheralAccess.revoked_at.is_(None))
    result = []
    for access in db.scalars(q.order_by(AssetPeripheralAccess.id)):
        item = asdict(access)
        item["peripheral"] = asdict(db.get(SharedPeripheral, access.peripheral_id))
        result.append(item)
    return result


@app.post("/api/assets/{asset_id}/peripherals", status_code=201)
def grant_peripheral(asset_id: int, data: PeripheralGrant,
                     db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    asset = require_asset(db, asset_id)
    peripheral = db.get(SharedPeripheral, data.peripheral_id)
    if not peripheral or peripheral.oi_id != asset.oi_id:
        raise HTTPException(422, "МФУ должно принадлежать тому же ОИ")
    duplicate = db.scalar(select(AssetPeripheralAccess).where(
        AssetPeripheralAccess.asset_id == asset_id, AssetPeripheralAccess.peripheral_id == data.peripheral_id,
        AssetPeripheralAccess.revoked_at.is_(None)))
    if duplicate:
        raise HTTPException(409, "Разрешение уже действует")
    if data.driver_document_id:
        check_document(db, data.driver_document_id)
    item = AssetPeripheralAccess(asset_id=asset_id, created_by=user.id, **data.model_dump())
    db.add(item)
    db.flush()
    audit(db, user, "peripheral_allowed", "asset", asset_id, {"peripheral_id": data.peripheral_id, "connection_type":data.connection_type, "driver_name":data.driver_name, "driver_version":data.driver_version, "driver_sha256":data.driver_sha256})
    commit(db)
    return asdict(item)


@app.post("/api/assets/{asset_id}/peripherals/{access_id}/revoke")
def revoke_peripheral(asset_id: int, access_id: int, data: RetireInput,
                      db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    require_asset(db, asset_id)
    item = require_record(db, AssetPeripheralAccess, access_id, asset_id)
    if item.revoked_at:
        raise HTTPException(409, "Разрешение уже отозвано")
    item.revoked_at = now()
    item.reason = f"{item.reason}\nОТЗЫВ: {data.reason}"
    audit(db, user, "peripheral_revoked", "asset", asset_id, {"access_id": access_id, "reason": data.reason})
    commit(db)
    return asdict(item)


@app.get("/api/assets/{asset_id}/security-tools")
def list_security_tools(asset_id: int, current_only: bool = False,
                        db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    require_asset(db, asset_id)
    q = select(AssetSecurityTool).where(AssetSecurityTool.asset_id == asset_id)
    if current_only:
        q = q.where(AssetSecurityTool.removed_at.is_(None))
    return [asdict(x) for x in db.scalars(q.order_by(AssetSecurityTool.id))]


@app.post("/api/assets/{asset_id}/security-tools", status_code=201)
def install_security_tool(asset_id: int, data: SecurityToolCreate,
                          db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    require_asset(db, asset_id)
    check_document(db, data.document_id)
    if data.expires_on:
        try:
            from datetime import date
            date.fromisoformat(data.expires_on)
        except ValueError:
            raise HTTPException(422, "Недопустимая дата завершения действия")
    item = AssetSecurityTool(asset_id=asset_id, created_by=user.id, **data.model_dump())
    db.add(item)
    db.flush()
    audit(db, user, "security_tool_installed", "asset", asset_id, {"tool_id": item.id})
    commit(db)
    return asdict(item)


@app.post("/api/assets/{asset_id}/security-tools/{tool_id}/remove")
def remove_security_tool(asset_id: int, tool_id: int, data: RetireInput,
                         db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    require_asset(db, asset_id)
    item = require_record(db, AssetSecurityTool, tool_id, asset_id)
    if item.removed_at:
        raise HTTPException(409, "Средство уже выведено из состава")
    item.removed_at, item.removal_reason = now(), data.reason
    audit(db, user, "security_tool_removed", "asset", asset_id, {"tool_id": item.id, "reason": data.reason})
    commit(db)
    return asdict(item)


@app.get("/api/assets/{asset_id}/requests")
def list_service_requests(asset_id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    require_asset(db, asset_id)
    return [asdict(x) for x in db.scalars(select(ServiceRequest).where(
        ServiceRequest.asset_id == asset_id).order_by(ServiceRequest.id.desc()))]


@app.post("/api/assets/{asset_id}/requests", status_code=201)
def add_service_request(asset_id: int, data: ServiceRequestCreate,
                        db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    require_asset(db, asset_id)
    check_document(db, data.document_id)
    item = ServiceRequest(asset_id=asset_id, reporter=data.reporter, subject=data.subject,
                          fault_description=data.fault_description, reported_at=safe_event_time(data.reported_at),
                          document_id=data.document_id, openproject_work_package_id=data.openproject_work_package_id,
                          created_by=user.id)
    db.add(item)
    db.flush()
    audit(db, user, "service_requested", "asset", asset_id, {"request_id": item.id})
    commit(db)
    return asdict(item)


@app.post("/api/assets/{asset_id}/requests/{request_id}/close")
def close_service_request(asset_id: int, request_id: int, data: ServiceRequestClose,
                          db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    require_asset(db, asset_id)
    item = require_record(db, ServiceRequest, request_id, asset_id)
    if item.status != "open":
        raise HTTPException(409, "Обращение уже закрыто")
    work = db.scalar(select(WorkEntry).where(
        WorkEntry.service_request_id == request_id, WorkEntry.asset_id == asset_id,
        WorkEntry.seal_state_after != "unknown").order_by(WorkEntry.id.desc()))
    if work is None:
        raise HTTPException(409, "Для закрытия нужна запись о выполненных работах и состоянии опечатывания")
    item.status = "closed"
    item.closed_at = now()
    audit(db, user, "service_closed", "asset", asset_id, {"request_id": item.id, "resolution": data.resolution})
    commit(db)
    return asdict(item)


@app.get("/api/assets/{asset_id}/works")
def list_work_entries(asset_id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    require_asset(db, asset_id)
    return [asdict(x) for x in db.scalars(select(WorkEntry).where(
        WorkEntry.asset_id == asset_id).order_by(WorkEntry.performed_at.desc(), WorkEntry.id.desc()))]


@app.post("/api/assets/{asset_id}/works", status_code=201)
def add_work_entry(asset_id: int, data: WorkEntryCreate,
                   db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    asset = require_asset(db, asset_id)
    check_document(db, data.document_id)
    if data.service_request_id:
        req = require_record(db, ServiceRequest, data.service_request_id, asset_id)
        if req.status == "closed":
            raise HTTPException(409, "Обращение уже закрыто")
    if data.document_page is not None and data.document_id is None:
        raise HTTPException(422, "Для указания страницы нужен документ")
    if data.seal_state_after in {"opened", "unsealed_after_repair", "seal_damaged"} and len(data.seal_note.strip()) < 8:
        raise HTTPException(422, "Укажите причину вскрытия или отсутствия пломбы")
    if data.work_type in {"repair", "replacement"} and data.seal_state_after == "unknown":
        raise HTTPException(422, "После ремонта или замены обязательно зафиксируйте состояние корпуса")
    item = WorkEntry(asset_id=asset_id, service_request_id=data.service_request_id,
                     performed_at=safe_event_time(data.performed_at), performer=data.performer,
                     work_type=data.work_type, actions=data.actions, result=data.result,
                     seal_state_after=data.seal_state_after, seal_note=data.seal_note,
                     document_id=data.document_id, document_page=data.document_page, created_by=user.id)
    db.add(item)
    if data.seal_state_after != "unknown":
        asset.seal_state = data.seal_state_after
        new_revision(db, user, "asset", asset_id, "seal_state", asset.seal_state)
    db.flush()
    audit(db, user, "work_recorded", "asset", asset_id, {"work_id": item.id, "performed_by": data.performer,
                                                           "seal_state_after": data.seal_state_after, "actions":data.actions, "result":data.result})
    commit(db)
    return asdict(item)


@app.get("/api/assets/{asset_id}/inspections")
def list_inspections(asset_id: int, db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    require_asset(db, asset_id)
    result = []
    for item in db.scalars(select(AssetInspection).where(
            AssetInspection.asset_id == asset_id).order_by(AssetInspection.inspected_at.desc(), AssetInspection.id.desc())):
        row = asdict(item)
        row["quarter"] = f"{item.inspected_at.year}-Q{(item.inspected_at.month-1)//3+1}"
        result.append(row)
    return result


@app.post("/api/assets/{asset_id}/inspections", status_code=201)
def add_inspection(asset_id: int, data: InspectionCreate,
                   db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    require_asset(db, asset_id)
    check_document(db, data.document_id)
    if data.document_page is not None and data.document_id is None:
        raise HTTPException(422, "Для указания страницы нужен документ")
    if not data.checklist or set(data.checklist) - INSPECTION_CHECKS:
        raise HTTPException(422, "Неверный состав контрольного листа")
    if set(data.violation_categories) - INSPECTION_CATEGORIES:
        raise HTTPException(422, "Недопустимая категория нарушения")
    if data.status == "passed" and not any(v == "ok" for v in data.checklist.values()):
        raise HTTPException(422, "Необходимо выполнить хотя бы один пункт проверки")
    if data.status == "passed" and (data.violation_categories or "violation" in data.checklist.values()):
        raise HTTPException(422, "Нельзя считать проверку успешной при зарегистрированных нарушениях")
    if data.status == "violations" and not data.violation_categories:
        raise HTTPException(422, "Укажите категорию выявленного нарушения")
    item = AssetInspection(asset_id=asset_id, inspected_at=safe_event_time(data.inspected_at),
                           inspector=data.inspector, subject_user=data.subject_user, checklist=data.checklist,
                           violation_categories=data.violation_categories,
                           finding_summary=data.finding_summary, corrective_action=data.corrective_action,
                           status=data.status, document_id=data.document_id, document_page=data.document_page, created_by=user.id)
    db.add(item)
    db.flush()
    audit(db, user, "inspection_recorded", "asset", asset_id,
          {"inspection_id": item.id, "status": item.status, "categories": item.violation_categories})
    commit(db)
    return asdict(item)


@app.get("/api/inspections/quarterly-status")
def quarterly_status(oi_id: int | None = None, year: int | None = Query(default=None, ge=2020, le=2100),
                     quarter: int | None = Query(default=None, ge=1, le=4),
                     db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    t = now()
    year, quarter = year or t.year, quarter or ((t.month-1)//3+1)
    from datetime import datetime as dt
    start = dt(year, 3*(quarter-1)+1, 1, tzinfo=timezone.utc)
    end = dt(year+1, 1, 1, tzinfo=timezone.utc) if quarter == 4 else dt(year, 3*quarter+1, 1, tzinfo=timezone.utc)
    assets = db.scalars(select(Asset).where(Asset.oi_id == oi_id).order_by(Asset.id)) if oi_id else db.scalars(select(Asset).order_by(Asset.id))
    result = []
    for asset in assets:
        inspections = list(db.scalars(select(AssetInspection).where(
            AssetInspection.asset_id == asset.id, AssetInspection.inspected_at >= start,
            AssetInspection.inspected_at < end).order_by(AssetInspection.inspected_at.desc())))
        result.append({"asset_id": asset.id, "asset_code": asset.code, "oi_id": asset.oi_id,
                       "inspected": bool(inspections), "last_result": inspections[0].status if inspections else None,
                       "inspection_count": len(inspections)})
    return {"year": year, "quarter": quarter, "start": start, "end": end, "results": result,
            "not_checked": sum(not x["inspected"] for x in result)}


# ---- v0.3: identity administration, OI submissions, attestation watch, weekly report ----
class NewUserInput(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r'^[a-zA-Z0-9._-]+$')
    display_name: str = Field(min_length=2, max_length=180)
    role: Literal['admin','editor','requester']
    initial_password: str = Field(min_length=12, max_length=256)

class ChangeUserInput(BaseModel):
    role: Literal['admin','editor','requester'] | None = None
    active: bool | None = None
    display_name: str | None = Field(default=None, min_length=2, max_length=180)

class ChangePasswordInput(BaseModel):
    old_password: str
    new_password: str = Field(min_length=12, max_length=256)

class ProposalInput(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=250)
    classification: str = Field(default='', max_length=250)
    location: str = Field(default='', max_length=250)
    notes: str = Field(default='', max_length=4000)
    document_id: int | None = Field(default=None, ge=1)

class ProposalReview(BaseModel):
    decision: Literal['approved','rejected']
    review_note: str = Field(min_length=10, max_length=4000)

@app.get('/api/users')
def list_users(db: DBSession=Depends(get_db), user:User=Depends(admin_only)):
    return [{'id':x.id,'username':x.username,'display_name':x.display_name,'role':x.role,
             'active':x.active,'must_change_password':x.must_change_password,'created_at':x.created_at}
            for x in db.scalars(select(User).order_by(User.username))]

@app.post('/api/users',status_code=201)
def create_user(data:NewUserInput, db:DBSession=Depends(get_db), user:User=Depends(admin_only)):
    if db.scalar(select(User).where(User.username==data.username)):
        raise HTTPException(409,'Пользователь уже существует')
    record=User(username=data.username, display_name=data.display_name, role=data.role,
                password_hash=PASSWORD_HASHER.hash(data.initial_password), must_change_password=True, created_by=user.id)
    db.add(record)
    db.flush()
    audit(db,user,'user_created','user',record.id,{'username':record.username,'role':record.role})
    commit(db)
    return {'id':record.id,'username':record.username,'role':record.role,'must_change_password':True}

@app.patch('/api/users/{user_id}')
def update_user(user_id:int,data:ChangeUserInput,db:DBSession=Depends(get_db), user:User=Depends(admin_only)):
    record=db.get(User,user_id)
    if record is None:raise HTTPException(404,'Учётная запись не найдена')
    changes=data.model_dump(exclude_unset=True)
    if record.id==user.id and (changes.get('active') is False or changes.get('role','admin')!='admin'):
        raise HTTPException(409,'Нельзя отключить или лишить прав самого себя')
    if record.role=='admin' and (changes.get('active') is False or (changes.get('role') and changes['role']!='admin')):
        admins=db.scalar(select(func.count()).select_from(User).where(User.active.is_(True),User.role=='admin'))
        if admins<=1:raise HTTPException(409,'Нельзя отключить последнего администратора')
    before={'active':record.active,'role':record.role,'display_name':record.display_name}
    for k,v in changes.items():setattr(record,k,v)
    if 'active' in changes or 'role' in changes:
        for sess in db.scalars(select(LoginSession).where(LoginSession.user_id==record.id)):
            db.delete(sess)
    audit(db,user,'user_updated','user',record.id,{'before':before,'after':changes})
    commit(db)
    return {'id':record.id,'role':record.role,'active':record.active}

@app.post('/api/auth/password')
def change_password(data:ChangePasswordInput,db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    try: valid=PASSWORD_HASHER.verify(user.password_hash,data.old_password)
    except (VerifyMismatchError,VerificationError):valid=False
    if not valid: raise HTTPException(401,'Старый пароль неверен')
    if data.new_password==data.old_password:raise HTTPException(422,'Новый пароль должен отличаться от прежнего')
    user.password_hash=PASSWORD_HASHER.hash(data.new_password)
    user.must_change_password=False
    audit(db,user,'password_changed','user',user.id)
    commit(db)
    return {'ok':True}

@app.post('/api/proposals',status_code=201)
def create_proposal(data:ProposalInput,db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    if user.role not in ('admin','editor','requester'):
        raise HTTPException(403,'Недостаточно прав')
    if data.document_id:
        check_document(db,data.document_id)
        doc=db.get(Document,data.document_id)
        if user.role=='requester' and doc.created_by!=user.id:
            raise HTTPException(403,'Нельзя прикреплять чужие документы')
    rec=OIProposal(requester_id=user.id,**data.model_dump())
    db.add(rec);db.flush()
    audit(db,user,'proposal_submitted','proposal',rec.id,{'code':rec.code,'name':rec.name,'document_id':rec.document_id})
    commit(db)
    return asdict(rec)

@app.post('/api/proposals/{proposal_id}/attachment',status_code=201)
async def proposal_attachment(proposal_id:int,file:UploadFile=File(...),
                              db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    rec=db.get(OIProposal,proposal_id)
    if rec is None:raise HTTPException(404,'Заявка не найдена')
    if user.role=='requester' and rec.requester_id!=user.id:
        raise HTTPException(403,'Нельзя редактировать чужую заявку')
    if rec.status!='submitted':raise HTTPException(409,'Рассмотренная заявка не изменяется')
    filename=Path(file.filename or '').name
    if not filename or len(filename)>255:raise HTTPException(422,'Укажите корректное имя файла')
    content=await file.read(MAX_FILE_SIZE+1)
    if len(content)>MAX_FILE_SIZE:raise HTTPException(413,'Файл больше 25 МБ')
    extension=valid_file_type(filename,content)
    key=secrets.token_hex(24)
    DOCUMENT_ROOT.mkdir(parents=True,exist_ok=True)
    path=DOCUMENT_ROOT/key
    path.write_bytes(content)
    try:
        doc=Document(title=f'Заявка #{rec.id}: {filename}',original_filename=filename,storage_key=key,
           content_type={'.pdf':'application/pdf','.txt':'text/plain','.md':'text/plain','.csv':'text/csv'}.get(extension,'application/octet-stream'),
           sha256=hashlib.sha256(content).hexdigest(),size_bytes=len(content),created_by=user.id)
        db.add(doc);db.flush()
        previous=rec.document_id
        rec.document_id=doc.id
        audit(db,user,'proposal_attachment','proposal',rec.id,{'document_id':doc.id,'previous_document_id':previous,'sha256':doc.sha256})
        commit(db)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {'document_id':doc.id,'sha256':doc.sha256}

@app.get('/api/proposals/{proposal_id}/attachment/file')
def proposal_attachment_file(proposal_id:int,db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    rec=db.get(OIProposal,proposal_id)
    if rec is None or rec.document_id is None:raise HTTPException(404,'Документ не найден')
    if user.role=='requester' and rec.requester_id!=user.id:
        raise HTTPException(403,'Доступ запрещён')
    doc=db.get(Document,rec.document_id)
    path=DOCUMENT_ROOT/doc.storage_key
    if not path.is_file():raise HTTPException(404,'Файл отсутствует')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=doc.sha256:
        raise HTTPException(409,'Контрольная сумма не совпадает')
    return FileResponse(path,media_type=doc.content_type,filename=doc.original_filename,
        content_disposition_type='inline' if doc.content_type=='application/pdf' else 'attachment',
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':'sandbox'})

@app.get('/api/proposals')
def list_proposals(db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    stmt=select(OIProposal).order_by(OIProposal.id.desc())
    if user.role=='requester':stmt=stmt.where(OIProposal.requester_id==user.id)
    return [asdict(x) for x in db.scalars(stmt.limit(1000))]

@app.post('/api/proposals/{proposal_id}/review')
def review_proposal(proposal_id:int,data:ProposalReview,db:DBSession=Depends(get_db),user:User=Depends(editor_or_admin)):
    rec=db.get(OIProposal,proposal_id)
    if not rec:raise HTTPException(404,'Заявка не найдена')
    if rec.status!='submitted':raise HTTPException(409,'Заявка уже рассмотрена')
    if data.decision=='approved':
        if db.scalar(select(InformationObject).where(InformationObject.code==rec.code)):
            raise HTTPException(409,'ОИ с таким кодом уже существует')
        obj=InformationObject(code=rec.code,name=rec.name,classification=rec.classification,
                              location=rec.location,notes=rec.notes,status='formation')
        db.add(obj);db.flush();rec.created_oi_id=obj.id
        audit(db,user,'create_from_proposal','oi',obj.id,{'proposal_id':rec.id,'code':obj.code})
    rec.status=data.decision;rec.review_note=data.review_note;rec.reviewed_by=user.id;rec.reviewed_at=now()
    audit(db,user,'proposal_reviewed','proposal',rec.id,{'decision':data.decision,'note':data.review_note,'oi_id':rec.created_oi_id})
    commit(db)
    return asdict(rec)

def attestation_status(obj, today):
    if not obj.attestation_valid_until: return 'not_set'
    days=(obj.attestation_valid_until-today).days
    return 'expired' if days<0 else ('due_soon' if days<=obj.attestation_notice_days else 'valid')

@app.get('/api/attestations/due')
def due_attestations(db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    today=datetime.now(LOCAL_TIMEZONE).date()
    records=db.scalars(select(InformationObject).where(InformationObject.attestation_valid_until.is_not(None)).order_by(InformationObject.attestation_valid_until))
    rows=[]
    for obj in records:
        status=attestation_status(obj,today)
        if status in ('due_soon','expired'):
            rows.append({'id':obj.id,'code':obj.code,'name':obj.name,'valid_until':obj.attestation_valid_until.isoformat(),
                         'days_left':(obj.attestation_valid_until-today).days,'status':status,
                         'notice_days':obj.attestation_notice_days,'openproject_project_id':obj.openproject_project_id})
    return {'as_of':today.isoformat(),'items':rows,'count':len(rows)}

@app.get('/api/reports/weekly')
def weekly_report(week_start:date|None=None,user_id:int|None=None,format:Literal['json','csv']='json',
                  db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    today=datetime.now(LOCAL_TIMEZONE).date()
    start=week_start or today-timedelta(days=today.weekday())
    if start.weekday()!=0:raise HTTPException(422,'Начало отчётной недели должно быть понедельником')
    target=user_id or user.id
    if target!=user.id and user.role!='admin':raise HTTPException(403,'Чужой отчёт доступен только администратору')
    person=db.get(User,target)
    if person is None:raise HTTPException(404,'Учётная запись не найдена')
    start_local=datetime(start.year,start.month,start.day,tzinfo=LOCAL_TIMEZONE)
    end_local=start_local+timedelta(days=7)
    start_utc=start_local.astimezone(timezone.utc);end_utc=end_local.astimezone(timezone.utc)
    actions=list(db.scalars(select(AuditEvent).where(AuditEvent.actor_id==target,
        AuditEvent.created_at>=start_utc,AuditEvent.created_at<end_utc).order_by(AuditEvent.created_at,AuditEvent.id)))
    jobs=list(db.scalars(select(WorkEntry).where(WorkEntry.created_by==target,
        WorkEntry.created_at>=start_utc,WorkEntry.created_at<end_utc).order_by(WorkEntry.created_at)))
    inspections=list(db.scalars(select(AssetInspection).where(AssetInspection.created_by==target,
        AssetInspection.created_at>=start_utc,AssetInspection.created_at<end_utc).order_by(AssetInspection.created_at)))
    report={'user':{'id':person.id,'username':person.username,'display_name':person.display_name},
            'week_start':start.isoformat(),'week_end':(start+timedelta(days=6)).isoformat(),
            'timezone':str(LOCAL_TIMEZONE),
            'work_entries':[{'id':x.id,'asset_id':x.asset_id,'performed_at':x.performed_at,'performer_declared':x.performer,
                             'actions':x.actions,'result':x.result} for x in jobs],
            'inspections':[{'id':x.id,'asset_id':x.asset_id,'inspected_at':x.inspected_at,'status':x.status} for x in inspections],
            'activity':[{'at':x.created_at,'action':x.action,'entity_type':x.entity_type,'entity_id':x.entity_id,
                         'details':x.details} for x in actions]}
    if format=='json':return report
    stream=io.StringIO(newline='');writer=csv.writer(stream,delimiter=';')
    writer.writerow(['Дата регистрации','Действие','Тип сущности','ID','Описание'])
    for x in actions:
        content=json.dumps(x.details,ensure_ascii=False)
        def safe(v):
            v=str(v)
            return "'"+v if v.lstrip().startswith(('=','+','-','@','\t','\r')) else v
        writer.writerow([safe(x.created_at.isoformat()),safe(x.action),safe(x.entity_type),x.entity_id,safe(content)])
    audit(db,user,'weekly_report_exported','report',target,{'week_start':start.isoformat(),'actions_count':len(actions)})
    commit(db)
    return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',headers={
        'Content-Disposition':f'attachment; filename="oi-week-{start.isoformat()}-user-{target}.csv"',
        'Cache-Control':'no-store'})


# ---- v0.4 automated local controls and explicitly opt-in OpenProject outbox ----
from app.automation import plan as plan_controls
from app.openproject_client import configuration as op_configuration, enabled as op_sync_enabled, publish as op_publish, fetch_work_package as op_fetch_work_package

@app.get('/api/automation/preview')
def automation_preview(db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    return plan_controls(db,datetime.now(LOCAL_TIMEZONE).date(),write=False)

@app.post('/api/automation/plan')
def automation_plan(db:DBSession=Depends(get_db),user:User=Depends(editor_or_admin)):
    result=plan_controls(db,datetime.now(LOCAL_TIMEZONE).date(),write=True)
    audit(db,user,'controls_planned','automation',0,{'new_count':result['new_count']})
    commit(db)
    return result

@app.get('/api/automation/activities')
def automation_activities(status:str|None=None,event_type:str|None=None,oi_id:int|None=None,
                          limit:int=Query(200,ge=1,le=1000),offset:int=Query(0,ge=0),
                          db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    query=select(PlannedActivity)
    if status == 'pending':
        query=query.where(PlannedActivity.status.in_(['open','acknowledged']))
    elif status:query=query.where(PlannedActivity.status==status)
    if event_type:query=query.where(PlannedActivity.event_type==event_type)
    if oi_id:query=query.where(PlannedActivity.oi_id==oi_id)
    return [asdict(x) for x in db.scalars(query.order_by(PlannedActivity.deadline,PlannedActivity.id).offset(offset).limit(limit))]

class ActivityNote(BaseModel):
    note: str=Field(min_length=10,max_length=1000)

@app.post('/api/automation/activities/{id}/acknowledge')
def automation_acknowledge(id:int,data:ActivityNote,db:DBSession=Depends(get_db),
                           user:User=Depends(editor_or_admin)):
    item=db.get(PlannedActivity,id)
    if item is None:raise HTTPException(404,'Мероприятие не найдено')
    if item.status!='open':raise HTTPException(409,'Можно отметить только открытое мероприятие')
    item.status='acknowledged'
    audit(db,user,'control_acknowledged','planned_activity',item.id,{'note':data.note})
    commit(db)
    return asdict(item)

@app.get('/api/automation/integration')
def automation_integration(user:User=Depends(admin_only)):
    return {'enabled':op_sync_enabled(), 'configured':all(os.getenv(k) for k in ('OI_OP_BASE_URL','OI_OP_API_KEY','OI_OP_TYPE_ID')),
            'mode':'manual_review_only','secret_exposed':False}

@app.post('/api/automation/activities/{id}/publish')
def automation_publish(id:int,db:DBSession=Depends(get_db),user:User=Depends(admin_only)):
    item=db.get(PlannedActivity,id)
    if item is None:raise HTTPException(404,'Мероприятие не найдено')
    if item.status!='open':raise HTTPException(409,'Мероприятие уже закрыто или подтверждено')
    if item.sync_status!='not_sent':raise HTTPException(409,'Уже отправлялось — проверьте OpenProject перед повторением')
    try: op_configuration()
    except ValueError as err:raise HTTPException(409,str(err)) from err
    if item.openproject_project_id is None:raise HTTPException(409,'Нет ID проекта OpenProject')
    # Reserve before external side effect. Any failed/uncertain POST requires manual review.
    item.sync_status='needs_review';item.last_sync_at=now();item.sync_error='Ожидает сверки в OpenProject'
    audit(db,user,'control_publish_attempt','planned_activity',item.id,{'key':item.event_key})
    commit(db)
    try:
        wid=op_publish(item)
    except Exception as err:
        # Do not leak secrets or URLs from exception, and do not blindly retry after timeout.
        item.sync_error=f'Ошибка публикации ({type(err).__name__}); проверьте задачу по ключу в OpenProject'
        commit(db)
        raise HTTPException(502,item.sync_error) from None
    item.openproject_work_package_id=wid
    item.sync_status='published';item.sync_error=''
    audit(db,user,'control_published','planned_activity',item.id,{'openproject_work_package_id':wid})
    commit(db)
    return asdict(item)


# ---- v0.5 configurable periodic controls with evidence and safe status lookup ----
class ControlRuleInput(BaseModel):
    title: str = Field(min_length=3, max_length=250)
    scope: Literal['oi', 'asset']
    oi_id: int | None = Field(default=None, ge=1)
    first_due: date
    interval_months: Literal[1, 3, 6, 12]
    assignee: str = Field(default='', max_length=180)

    @field_validator('title')
    @classmethod
    def meaningful_title(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError('Нужно осмысленное название регламента')
        return value


class ControlCompletion(BaseModel):
    evidence_document_id: int = Field(ge=1)
    note: str = Field(min_length=10, max_length=2000)

    @field_validator('note')
    @classmethod
    def meaningful_note(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError('Опишите фактическое выполнение не менее чем 10 символами')
        return value


@app.get('/api/automation/rules')
def list_control_rules(db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    return [asdict(x) for x in db.scalars(select(ControlRule).order_by(ControlRule.id))]


@app.post('/api/automation/rules', status_code=201)
def create_control_rule(data: ControlRuleInput, db: DBSession = Depends(get_db),
                        user: User = Depends(admin_only)):
    if data.oi_id is not None and db.get(InformationObject, data.oi_id) is None:
        raise HTTPException(404, 'ОИ не найден')
    rule = ControlRule(**data.model_dump(), created_by=user.id)
    db.add(rule)
    db.flush()
    audit(db, user, 'control_rule_created', 'control_rule', rule.id,
          {'scope': rule.scope, 'oi_id': rule.oi_id, 'interval_months': rule.interval_months})
    commit(db)
    return asdict(rule)


@app.post('/api/automation/rules/{id}/disable')
def disable_control_rule(id: int, db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    rule = db.get(ControlRule, id)
    if rule is None:
        raise HTTPException(404, 'Правило не найдено')
    if not rule.active:
        raise HTTPException(409, 'Правило уже выключено')
    rule.active = False
    changed = 0
    for item in db.scalars(select(PlannedActivity).where(PlannedActivity.rule_id == id,
                                                        PlannedActivity.status.in_(['open', 'acknowledged']))):
        item.status = 'superseded'
        changed += 1
        if item.sync_status == 'published':
            item.sync_error = 'Правило выключено; задачу OpenProject необходимо сверить вручную'
    audit(db, user, 'control_rule_disabled', 'control_rule', id, {'superseded_count': changed})
    commit(db)
    return {'id': id, 'active': False, 'superseded_count': changed}


@app.post('/api/automation/rules/{id}/enable')
def enable_control_rule(id: int, db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    rule = db.get(ControlRule, id)
    if rule is None:
        raise HTTPException(404, 'Правило не найдено')
    if rule.active:
        raise HTTPException(409, 'Правило уже активно')
    rule.active = True
    # Previous superseded records stay in history; users can start new periods.
    audit(db, user, 'control_rule_enabled', 'control_rule', id)
    commit(db)
    return asdict(rule)


@app.get('/api/automation/summary')
def control_summary(db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    today = datetime.now(LOCAL_TIMEZONE).date()
    records = list(db.scalars(select(PlannedActivity)))
    pending = [x for x in records if x.status in ('open', 'acknowledged')]
    by_oi = {}
    for item in pending:
        slot = by_oi.setdefault(item.oi_id, {'oi_id': item.oi_id, 'pending': 0, 'overdue': 0, 'due_30_days': 0})
        slot['pending'] += 1
        if item.deadline < today:
            slot['overdue'] += 1
        if today <= item.deadline <= today + timedelta(days=30):
            slot['due_30_days'] += 1
    return {'as_of': today.isoformat(), 'total': len(records), 'pending': len(pending),
            'overdue': sum(x.deadline < today for x in pending),
            'due_30_days': sum(today <= x.deadline <= today + timedelta(days=30) for x in pending),
            'completed': sum(x.status == 'completed' for x in records),
            'by_oi': sorted(by_oi.values(), key=lambda x: (-x['overdue'], -x['pending'], x['oi_id']))}


@app.post('/api/automation/activities/{id}/complete')
def complete_control(id: int, data: ControlCompletion, db: DBSession = Depends(get_db),
                     user: User = Depends(editor_or_admin)):
    item = db.get(PlannedActivity, id)
    if item is None:
        raise HTTPException(404, 'Мероприятие не найдено')
    if item.status not in ('open', 'acknowledged'):
        raise HTTPException(409, 'Мероприятие уже закрыто или отменено')
    if db.get(Document, data.evidence_document_id) is None:
        raise HTTPException(404, 'Подтверждающий документ не найден')
    item.status = 'completed'
    item.evidence_document_id = data.evidence_document_id
    item.completion_note = data.note
    item.completed_by = user.id
    item.completed_at = now()
    audit(db, user, 'control_completed', 'planned_activity', item.id,
          {'evidence_document_id': data.evidence_document_id, 'note': data.note})
    commit(db)
    return asdict(item)


@app.post('/api/automation/activities/{id}/reconcile')
def reconcile_control(id: int, db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    item = db.get(PlannedActivity, id)
    if item is None:
        raise HTTPException(404, 'Мероприятие не найдено')
    if item.sync_status != 'published' or not item.openproject_work_package_id:
        raise HTTPException(409, 'Нет опубликованной задачи для сверки')
    try:
        remote = op_fetch_work_package(item.openproject_work_package_id)
    except Exception as err:
        # Never reveal tokens, URLs or HTTP bodies from external service.
        audit(db, user, 'control_remote_check_failed', 'planned_activity', id,
              {'error_type': type(err).__name__})
        commit(db)
        raise HTTPException(502, 'Не удалось получить статус из OpenProject; проверьте настройки и доступ') from None
    item.remote_status = remote['status']
    item.remote_checked_at = now()
    audit(db, user, 'control_remote_checked', 'planned_activity', id,
          {'remote_status': remote['status'], 'work_package_id': item.openproject_work_package_id})
    commit(db)
    return {'activity': asdict(item), 'remote': remote,
            'note': 'OpenProject не закрывает мероприятие автоматически; приложите доказательство в OI Registry'}

# v0.6.1 administrative requests: separate from historical OI proposals and SVT repair requests.
import ipaddress


class SystemTypeInput(BaseModel):
    name: str = Field(min_length=2, max_length=180)


class SystemTypePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    active: bool | None = None


class RegistryRequestInput(BaseModel):
    segment: str = Field(default='', max_length=150)
    full_name: str = Field(min_length=2, max_length=180)
    ip_address: str = Field(default='', max_length=60)
    scan_smb_path: str = Field(default='', max_length=2048)
    asset_id: int | None = Field(default=None, ge=1)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator('ip_address')
    @classmethod
    def check_ip(cls, value):
        if value:
            ipaddress.ip_address(value)
        return value

    @field_validator('scan_smb_path')
    @classmethod
    def check_smb_path(cls, value):
        if value and not (value.startswith('\\\\') or value.lower().startswith('smb://')):
            raise ValueError('Укажите UNC \\\\server\\share\\file.pdf или smb://server/share/file.pdf')
        return value


@app.get('/api/system-types')
def get_system_types(db: DBSession = Depends(get_db), user: User = Depends(current_user)):
    return [asdict(x) for x in db.scalars(select(SystemType).order_by(SystemType.name))]


@app.post('/api/system-types', status_code=201)
def add_system_type(data: SystemTypeInput, db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    record = SystemType(name=data.name.strip())
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Такой тип системы уже существует')
    audit(db, user, 'system_type_created', 'system_type', record.id, {'name': record.name})
    commit(db)
    return asdict(record)


@app.patch('/api/system-types/{type_id}')
def edit_system_type(type_id: int, data: SystemTypePatch,
                     db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    record = db.get(SystemType, type_id)
    if record is None:
        raise HTTPException(404, 'Тип системы не найден')
    patch = data.model_dump(exclude_unset=True)
    before = {key: getattr(record, key) for key in patch}
    for key, value in patch.items():
        setattr(record, key, value.strip() if key == 'name' else value)
    audit(db, user, 'system_type_changed', 'system_type', type_id, {'before': before, 'after': patch})
    try:
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Такой тип системы уже существует')
    return asdict(record)


@app.get('/api/registry-requests')
def get_registry_requests(db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    stmt = (select(RegistryRequest, Asset.code)
            .outerjoin(Asset, RegistryRequest.asset_id == Asset.id)
            .order_by(RegistryRequest.id.desc()).limit(5000))
    # Historical system_type_id is retained in the DB, but not shown or required.
    rows = list(db.execute(stmt))
    ids = [req.id for req, _ in rows]
    custom = {item_id: {} for item_id in ids}
    if ids:
        for value in db.scalars(select(FieldValue).where(
                FieldValue.entity_type == 'request', FieldValue.entity_id.in_(ids))):
            custom[value.entity_id][str(value.field_id)] = value.value
    return [{**asdict(req), 'asset_code': asset_code or '', 'custom_fields': custom[req.id]}
            for req, asset_code in rows]


@app.post('/api/registry-requests', status_code=201)
def add_registry_request(data: RegistryRequestInput, db: DBSession = Depends(get_db),
                         user: User = Depends(editor_or_admin)):
    if data.asset_id is not None:
        require_asset(db, data.asset_id)
    custom = normalize_custom_fields(db, 'request', data.custom_fields, creating=True)
    record = RegistryRequest(**data.model_dump(exclude={'custom_fields'}), created_by=user.id)
    db.add(record)
    db.flush()
    store_custom_fields(db, user, 'request', record.id, custom)
    audit(db, user, 'registry_request_created', 'registry_request', record.id, data.model_dump())
    commit(db)
    return asdict(record)


@app.patch('/api/registry-requests/{request_id}')
def edit_registry_request(request_id: int, data: RegistryRequestInput,
                          db: DBSession = Depends(get_db), user: User = Depends(editor_or_admin)):
    record = db.get(RegistryRequest, request_id)
    if record is None:
        raise HTTPException(404, 'Заявка не найдена')
    if data.asset_id is not None:
        require_asset(db, data.asset_id)
    changes = data.model_dump(exclude={'custom_fields'})
    custom = normalize_custom_fields(db, 'request', data.custom_fields, entity_id=request_id)
    before = {key: getattr(record, key) for key in changes}
    for key, value in changes.items():
        setattr(record, key, value)
    store_custom_fields(db, user, 'request', request_id, custom)
    audit(db, user, 'registry_request_updated', 'registry_request', request_id, {'before': before, 'after': changes})
    commit(db)
    return asdict(record)


@app.post('/api/assets/import/preview')
async def asset_import_preview(file: UploadFile = File(...), mode: Literal['merge', 'copy', 'replace'] = Form(...),
                               db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    from app.asset_csv import MAX_BYTES, parse, compare, snapshot
    raw = await file.read(MAX_BYTES + 1)
    rows = parse(raw)
    comparisons = {m: compare(db, rows, m) for m in ('merge', 'copy', 'replace')}
    nonce = str(uuid.uuid4())
    phrase = 'ПОДТВЕРЖДАЮ СВТ ' + secrets.token_hex(4).upper()
    baseline = hashlib.sha256(json.dumps(snapshot(db, rows), ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    approval = TransferApproval(id=nonce, actor_id=user.id, object_code='__SVT_CSV__', mode=mode,
                                archive_digest=hashlib.sha256(raw).hexdigest(), baseline_digest=baseline,
                                confirm_digest=token_digest(phrase), expires_at=now() + timedelta(minutes=10))
    db.add(approval)
    commit(db)
    return {'plan_id': nonce, 'confirmation_phrase': phrase, 'selected': comparisons[mode],
            'comparisons': comparisons, 'expires_at': approval.expires_at.isoformat()}


@app.post('/api/assets/import/commit')
async def asset_import_commit(plan_id: str = Form(...), mode: Literal['merge', 'copy', 'replace'] = Form(...),
                              confirmation_phrase: str = Form(...), file: UploadFile = File(...),
                              db: DBSession = Depends(get_db), user: User = Depends(admin_only)):
    from app.asset_csv import MAX_BYTES, parse, compare, snapshot, apply
    raw = await file.read(MAX_BYTES + 1)
    rows = parse(raw)
    approval = db.scalar(select(TransferApproval).where(TransferApproval.id == plan_id).with_for_update())
    if not approval or approval.actor_id != user.id or approval.object_code != '__SVT_CSV__':
        raise HTTPException(404, 'Предпросмотр не найден')
    expiry = approval.expires_at if approval.expires_at.tzinfo else approval.expires_at.replace(tzinfo=timezone.utc)
    if approval.used_at is not None or expiry <= now():
        raise HTTPException(409, 'Подтверждение истекло или уже использовано')
    if approval.mode != mode or not hmac.compare_digest(approval.archive_digest, hashlib.sha256(raw).hexdigest()):
        raise HTTPException(409, 'Файл или режим изменились')
    if not hmac.compare_digest(approval.confirm_digest, token_digest(confirmation_phrase)):
        raise HTTPException(403, 'Нужно повторное подтверждение')
    # Lock matching rows before computing the state and executing. Unique codes guard concurrent inserts.
    list(db.scalars(select(Asset).where(Asset.code.in_(r['code'] for r in rows)).with_for_update()))
    baseline = hashlib.sha256(json.dumps(snapshot(db, rows), ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    if not hmac.compare_digest(baseline, approval.baseline_digest):
        raise HTTPException(409, 'Реестр изменился после предпросмотра — повторите проверку')
    outcome = compare(db, rows, mode, plan_id.replace('-', ''))
    if not outcome['can_apply']:
        raise HTTPException(409, {'conflicts': outcome['conflicts']})
    try:
        apply(db, rows, mode, plan_id.replace('-', ''))
        approval.used_at = now()
        audit(db, user, 'asset_csv_import', 'asset', 0, {'plan_id': plan_id, 'mode': mode,
              'sha256': approval.archive_digest, 'summary': {k: outcome[k] for k in ('total', 'add', 'update')}})
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Конкурирующий импорт изменил реестр. Создайте новый предпросмотр.')
    return {'ok': True, 'mode': mode, **outcome}

# v0.7.0: filter-builder uses server allowlists and does not execute user SQL.
class AssetQueryFilter(BaseModel):
    field: str
    op: Literal['eq','contains','empty','not_empty']
    value: str = Field(default='', max_length=250)

class AssetQueryRequest(BaseModel):
    columns: list[str] = Field(min_length=1, max_length=40)
    filters: list[AssetQueryFilter] = Field(default_factory=list, max_length=8)

@app.post('/api/assets/query/preview')
def preview_asset_query(data: AssetQueryRequest,db: DBSession=Depends(get_db),user: User=Depends(current_user)):
    from app.asset_query import rows
    return rows(db,data.columns,[f.model_dump() for f in data.filters],200)

@app.post('/api/assets/query/export.csv')
def export_asset_query(data: AssetQueryRequest,db:DBSession=Depends(get_db),user:User=Depends(current_user)):
    from app.asset_query import rows,to_csv
    result=rows(db,data.columns,[f.model_dump() for f in data.filters],20000)
    if result['truncated']:
        raise HTTPException(413,'В выборке больше 20 000 СВТ. Уточните фильтр.')
    audit(db,user,'asset_query_csv_export','asset',0,{'columns':data.columns,'filters':len(data.filters),'rows':len(result['rows'])})
    commit(db)
    return Response(to_csv(result).encode('utf-8'),media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition':'attachment; filename="svt-selected.csv"',
                             'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
