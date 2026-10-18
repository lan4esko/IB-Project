import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auth, catalog, database as dbm, schemas as s

require_key = auth.actor_dependency

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
OPENPROJECT_URL = os.getenv("OPENPROJECT_URL", "").rstrip("/")
OPENPROJECT_API_KEY = os.getenv("OPENPROJECT_API_KEY", "")
OPENPROJECT_CA_BUNDLE = os.getenv("OPENPROJECT_CA_BUNDLE", "")


def log(db: Session, kind: str, entity_id: int, action: str, actor: auth.Actor):
    db.add(dbm.AuditEvent(kind=kind, entity_id=entity_id, action=action,
                          actor_user_id=actor.id))


def must_exist(db: Session, cls, key: int):
    obj = db.get(cls, key)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"Объект {cls.__name__} не найден: {key}")
    return obj


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev bootstrap; replace with versioned Alembic migrations before production.
    if dbm.DATABASE_URL.startswith("sqlite"):
        dbm.Base.metadata.create_all(dbm.engine)
    yield


app = FastAPI(title="ИБ-платформа — backend (пилот)", version="0.3.0", lifespan=lifespan,
              description="Пилот с PostgreSQL, учётными записями, ролями и ACL объектов. Не для публикации в Интернет.")


@app.get("/health/live")
def liveness():
    return {"status": "ok", "version": "0.3.0"}


@app.get("/health/ready")
def readiness():
    try:
        with dbm.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            if dbm.engine.dialect.name == "postgresql":
                version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                if version != "0002_users_acl":
                    raise ValueError("Неожиданная версия схемы")
        return {"status": "ready", "database": dbm.engine.dialect.name}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="База данных не готова") from exc


@app.get("/api/v1/models/catalog", dependencies=[Depends(require_key)])
def catalog_list():
    return {"models": catalog.MODEL_CATALOG}


@app.get("/api/v1/models/installed", dependencies=[Depends(require_key)])
async def installed_models():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            return {"source": "ollama", "models": r.json().get("models", [])}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Ollama недоступна") from exc


@app.get("/api/v1/models/loaded", dependencies=[Depends(require_key)])
async def loaded_models():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{OLLAMA_URL}/api/ps")
            r.raise_for_status()
            return {"source": "ollama", "models": r.json().get("models", [])}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Ollama недоступна") from exc


@app.get("/api/v1/integrations/openproject/status", dependencies=[Depends(require_key)])
async def op_status(actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "security")
    if not OPENPROJECT_URL:
        return {"status": "not_configured"}
    op_auth = ("apikey", OPENPROJECT_API_KEY) if OPENPROJECT_API_KEY else None
    try:
        async with httpx.AsyncClient(timeout=8, verify=OPENPROJECT_CA_BUNDLE or True,
                                     follow_redirects=False, auth=op_auth, trust_env=False) as client:
            r = await client.get(f"{OPENPROJECT_URL}/api/v3/")
        return {"status": "reachable", "http_status": r.status_code,
                "authenticated": bool(op_auth) and r.status_code < 400}
    except httpx.HTTPError as exc:
        return {"status": "unreachable", "error_type": type(exc).__name__}


@app.get("/api/v1/integrations/openproject/projects", dependencies=[Depends(require_key)])
async def op_projects(actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "security")
    if not OPENPROJECT_URL or not OPENPROJECT_API_KEY:
        raise HTTPException(503, "OpenProject URL или API-ключ не настроен")
    try:
        async with httpx.AsyncClient(timeout=15, verify=OPENPROJECT_CA_BUNDLE or True,
                                     auth=("apikey", OPENPROJECT_API_KEY), trust_env=False) as client:
            r = await client.get(f"{OPENPROJECT_URL}/api/v3/projects", params={"pageSize": 20})
            r.raise_for_status()
            data = r.json()
            return {"count": data.get("count"), "projects": data.get("_embedded", {}).get("elements", [])}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Ошибка чтения проектов OpenProject") from exc


@app.post("/api/v1/acts", response_model=s.ActView, status_code=201, dependencies=[Depends(require_key)])
def create_act(value: s.ActCreate, db: Session = Depends(dbm.get_db),
               actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "security")
    if db.scalar(select(dbm.NormativeAct).where(dbm.NormativeAct.code == value.code,
                                                 dbm.NormativeAct.revision == value.revision)):
        raise HTTPException(409, "Такая редакция акта уже зарегистрирована")
    item = dbm.NormativeAct(**value.model_dump())
    try:
        db.add(item); db.flush(); log(db, "act", item.id, "create", actor); db.commit(); db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Такая редакция акта уже зарегистрирована") from exc
    return item


@app.get("/api/v1/acts", response_model=list[s.ActView], dependencies=[Depends(require_key)])
def list_acts(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db)):
    return db.scalars(select(dbm.NormativeAct).order_by(dbm.NormativeAct.id.desc()).limit(limit)).all()


@app.post("/api/v1/requirements", response_model=s.RequirementView, status_code=201,
          dependencies=[Depends(require_key)])
def create_requirement(value: s.RequirementCreate, db: Session = Depends(dbm.get_db),
                       actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "security")
    must_exist(db, dbm.NormativeAct, value.act_id)
    item = dbm.Requirement(**value.model_dump())
    db.add(item); db.flush(); log(db, "requirement", item.id, "create", actor); db.commit(); db.refresh(item)
    return item


@app.get("/api/v1/requirements", response_model=list[s.RequirementView], dependencies=[Depends(require_key)])
def list_requirements(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db)):
    return db.scalars(select(dbm.Requirement).order_by(dbm.Requirement.id.desc()).limit(limit)).all()


@app.post("/api/v1/objects", response_model=s.ObjectView, status_code=201,
          dependencies=[Depends(require_key)])
def create_obj(value: s.ObjectCreate, db: Session = Depends(dbm.get_db),
               actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "security", "operator")
    item = dbm.InfoObject(**value.model_dump())
    db.add(item); db.flush()
    if actor.id is not None:
        db.add(dbm.ObjectGrant(object_id=item.id, user_id=actor.id, permission="write"))
    log(db, "object", item.id, "create", actor)
    db.commit(); db.refresh(item)
    return item


@app.get("/api/v1/objects", response_model=list[s.ObjectView], dependencies=[Depends(require_key)])
def list_objs(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db),
              actor: auth.Actor = Depends(auth.actor_dependency)):
    stmt = select(dbm.InfoObject)
    if actor.role != "admin":
        stmt = stmt.where(dbm.InfoObject.id.in_(
            select(dbm.ObjectGrant.object_id).where(dbm.ObjectGrant.user_id == actor.id)))
    return db.scalars(stmt.order_by(dbm.InfoObject.id.desc()).limit(limit)).all()


@app.post("/api/v1/measures", response_model=s.MeasureView, status_code=201,
          dependencies=[Depends(require_key)])
def create_measure(value: s.MeasureCreate, db: Session = Depends(dbm.get_db),
                   actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "security", "operator")
    if not auth.may_access_object(db, actor, value.info_object_id, write=True):
        raise HTTPException(403, "Нет права записи в объект")
    must_exist(db, dbm.Requirement, value.requirement_id)
    must_exist(db, dbm.InfoObject, value.info_object_id)
    if value.status == "completed" and not (value.evidence_uri and value.reviewed_by):
        raise HTTPException(422, "Для статуса completed нужны evidence_uri и reviewed_by")
    item = dbm.Measure(**value.model_dump())
    db.add(item); db.flush(); log(db, "measure", item.id, "create", actor); db.commit(); db.refresh(item)
    return item


@app.get("/api/v1/measures", response_model=list[s.MeasureView], dependencies=[Depends(require_key)])
def list_measures(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db),
                  actor: auth.Actor = Depends(auth.actor_dependency)):
    stmt = select(dbm.Measure)
    if actor.role != "admin":
        stmt = stmt.where(dbm.Measure.info_object_id.in_(
            select(dbm.ObjectGrant.object_id).where(dbm.ObjectGrant.user_id == actor.id)))
    return db.scalars(stmt.order_by(dbm.Measure.id.desc()).limit(limit)).all()


@app.patch("/api/v1/measures/{measure_id}", response_model=s.MeasureView,
           dependencies=[Depends(require_key)])
def update_measure(measure_id: int, value: s.MeasureUpdate, db: Session = Depends(dbm.get_db),
                   actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "security", "operator")
    item = must_exist(db, dbm.Measure, measure_id)
    if not auth.may_access_object(db, actor, item.info_object_id, write=True):
        raise HTTPException(403, "Нет права записи в объект")
    for key, val in value.model_dump(exclude_unset=True).items():
        setattr(item, key, val)
    if item.status == "completed" and not (item.evidence_uri and item.reviewed_by):
        raise HTTPException(422, "Для статуса completed нужны evidence_uri и reviewed_by")
    log(db, "measure", item.id, "update", actor); db.commit(); db.refresh(item)
    return item


@app.get("/api/v1/audit", dependencies=[Depends(require_key)])
def list_audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db),
               actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "auditor")
    items = db.scalars(select(dbm.AuditEvent).order_by(dbm.AuditEvent.id.desc()).limit(limit)).all()
    return [{"id": x.id, "kind": x.kind, "entity_id": x.entity_id,
             "action": x.action, "actor_user_id": x.actor_user_id, "created_at": x.created_at} for x in items]


# Account provisioning is intentionally independent of Open WebUI accounts.
@app.post("/api/v1/auth/login")
def login(value: s.LoginRequest, db: Session = Depends(dbm.get_db)):
    user = db.scalar(select(dbm.User).where(dbm.User.username == value.username))
    if user is None or not user.is_active or not auth.verify_password(value.password, user.password_hash):
        raise HTTPException(401, "Неверный логин или пароль")
    token, expires = auth.new_session(db, user)
    return {"access_token": token, "token_type": "bearer", "expires_at": expires}


@app.get("/api/v1/auth/me")
def me(actor: auth.Actor = Depends(auth.actor_dependency)):
    return {"id": actor.id, "username": actor.username, "role": actor.role}


@app.post("/api/v1/auth/logout", status_code=204)
def logout(db: Session = Depends(dbm.get_db),
           actor: auth.Actor = Depends(auth.actor_dependency)):
    if actor.session_id is not None:
        session = db.get(dbm.UserSession, actor.session_id)
        session.revoked_at = dbm.now_utc()
        db.commit()
    return None


@app.post("/api/v1/auth/change-password", status_code=204)
def change_password(value: s.PasswordChange, db: Session = Depends(dbm.get_db),
                    actor: auth.Actor = Depends(auth.actor_dependency)):
    user = db.get(dbm.User, actor.id)
    if user is None or not auth.verify_password(value.current_password, user.password_hash):
        raise HTTPException(401, "Неверный текущий пароль")
    user.password_hash = auth.hash_password(value.new_password)
    for session in db.scalars(select(dbm.UserSession).where(
        dbm.UserSession.user_id == user.id, dbm.UserSession.revoked_at.is_(None))):
        session.revoked_at = dbm.now_utc()
    log(db, "user", user.id, "change_password", actor)
    db.commit()
    return None


@app.post("/api/v1/users", response_model=s.UserView, status_code=201)
def create_user(value: s.UserCreate, db: Session = Depends(dbm.get_db),
                actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin")
    if db.scalar(select(dbm.User).where(dbm.User.username == value.username)):
        raise HTTPException(409, "Пользователь уже существует")
    user = dbm.User(username=value.username, password_hash=auth.hash_password(value.password),
                    role=value.role, is_active=True)
    try:
        db.add(user); db.flush(); log(db, "user", user.id, "create", actor)
        db.commit(); db.refresh(user)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409, "Пользователь уже существует") from exc
    return user


@app.get("/api/v1/users", response_model=list[s.UserView])
def list_users(db: Session = Depends(dbm.get_db),
               actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin")
    return db.scalars(select(dbm.User).order_by(dbm.User.id)).all()


@app.patch("/api/v1/users/{user_id}", response_model=s.UserView)
def change_user(user_id: int, change: s.UserUpdate, db: Session = Depends(dbm.get_db),
                actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin")
    if user_id == actor.id:
        raise HTTPException(409, "Изменение собственной роли/активности запрещено")
    user = must_exist(db, dbm.User, user_id)
    fields = change.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(422, "Не указаны изменения")
    if any(val is None for val in fields.values()):
        raise HTTPException(422, "Не допускается null для роли или активности")
    for key, val in fields.items():
        setattr(user, key, val)
    log(db, "user", user.id, "update", actor)
    db.commit(); db.refresh(user)
    return user


@app.get("/api/v1/objects/{object_id}", response_model=s.ObjectView)
def get_obj(object_id: int, db: Session = Depends(dbm.get_db),
            actor: auth.Actor = Depends(auth.actor_dependency)):
    if not auth.may_access_object(db, actor, object_id):
        raise HTTPException(404, "Объект не найден")
    return must_exist(db, dbm.InfoObject, object_id)


@app.get("/api/v1/objects/{object_id}/acl", response_model=list[s.GrantView])
def get_acl(object_id: int, db: Session = Depends(dbm.get_db),
            actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin")
    must_exist(db, dbm.InfoObject, object_id)
    return db.scalars(select(dbm.ObjectGrant).where(dbm.ObjectGrant.object_id == object_id)).all()


@app.put("/api/v1/objects/{object_id}/acl/{user_id}", response_model=s.GrantView)
def put_acl(object_id: int, user_id: int, value: s.GrantCreate,
            db: Session = Depends(dbm.get_db), actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin")
    must_exist(db, dbm.InfoObject, object_id)
    must_exist(db, dbm.User, user_id)
    existing = db.scalar(select(dbm.ObjectGrant).where(
        dbm.ObjectGrant.object_id == object_id, dbm.ObjectGrant.user_id == user_id))
    if existing:
        existing.permission = value.permission
        grant = existing
    else:
        grant = dbm.ObjectGrant(object_id=object_id, user_id=user_id, permission=value.permission)
        db.add(grant)
    db.flush(); log(db, "acl", object_id, "grant", actor)
    db.commit(); db.refresh(grant)
    return grant


@app.delete("/api/v1/objects/{object_id}/acl/{user_id}", status_code=204)
def remove_acl(object_id: int, user_id: int, db: Session = Depends(dbm.get_db),
               actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin")
    existing = db.scalar(select(dbm.ObjectGrant).where(
        dbm.ObjectGrant.object_id == object_id, dbm.ObjectGrant.user_id == user_id))
    if existing is None:
        raise HTTPException(404, "Разрешение не найдено")
    db.delete(existing); log(db, "acl", object_id, "revoke", actor); db.commit()
    return None
