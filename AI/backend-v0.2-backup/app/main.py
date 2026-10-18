import hmac
import os
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import catalog, database as dbm, schemas as s

API_KEY = os.getenv("IB_PLATFORM_API_KEY", "")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
OPENPROJECT_URL = os.getenv("OPENPROJECT_URL", "").rstrip("/")
OPENPROJECT_API_KEY = os.getenv("OPENPROJECT_API_KEY", "")
OPENPROJECT_CA_BUNDLE = os.getenv("OPENPROJECT_CA_BUNDLE", "")


def require_key(x_api_key: str | None = Header(default=None)):
    if not API_KEY or not x_api_key or not hmac.compare_digest(API_KEY, x_api_key):
        raise HTTPException(status_code=401, detail="Неверный или отсутствующий API-ключ")


def log(db: Session, kind: str, entity_id: int, action: str):
    db.add(dbm.AuditEvent(kind=kind, entity_id=entity_id, action=action))


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


app = FastAPI(title="ИБ-платформа — backend (пилот)", version="0.2.0", lifespan=lifespan,
              description="Прототип реестров и интеграций. Без RBAC, OCR, RAG и синхронизации.")


@app.get("/health/live")
def liveness():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/health/ready")
def readiness():
    try:
        with dbm.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            if dbm.engine.dialect.name == "postgresql":
                version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                if version != "0001_initial":
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
async def op_status():
    if not OPENPROJECT_URL:
        return {"status": "not_configured"}
    auth = ("apikey", OPENPROJECT_API_KEY) if OPENPROJECT_API_KEY else None
    try:
        async with httpx.AsyncClient(timeout=8, verify=OPENPROJECT_CA_BUNDLE or True,
                                     follow_redirects=False, auth=auth, trust_env=False) as client:
            r = await client.get(f"{OPENPROJECT_URL}/api/v3/")
        return {"status": "reachable", "http_status": r.status_code,
                "authenticated": bool(auth) and r.status_code < 400}
    except httpx.HTTPError as exc:
        return {"status": "unreachable", "error_type": type(exc).__name__}


@app.get("/api/v1/integrations/openproject/projects", dependencies=[Depends(require_key)])
async def op_projects():
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
def create_act(value: s.ActCreate, db: Session = Depends(dbm.get_db)):
    if db.scalar(select(dbm.NormativeAct).where(dbm.NormativeAct.code == value.code,
                                                 dbm.NormativeAct.revision == value.revision)):
        raise HTTPException(409, "Такая редакция акта уже зарегистрирована")
    item = dbm.NormativeAct(**value.model_dump())
    try:
        db.add(item); db.flush(); log(db, "act", item.id, "create"); db.commit(); db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Такая редакция акта уже зарегистрирована") from exc
    return item


@app.get("/api/v1/acts", response_model=list[s.ActView], dependencies=[Depends(require_key)])
def list_acts(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db)):
    return db.scalars(select(dbm.NormativeAct).order_by(dbm.NormativeAct.id.desc()).limit(limit)).all()


@app.post("/api/v1/requirements", response_model=s.RequirementView, status_code=201,
          dependencies=[Depends(require_key)])
def create_requirement(value: s.RequirementCreate, db: Session = Depends(dbm.get_db)):
    must_exist(db, dbm.NormativeAct, value.act_id)
    item = dbm.Requirement(**value.model_dump())
    db.add(item); db.flush(); log(db, "requirement", item.id, "create"); db.commit(); db.refresh(item)
    return item


@app.get("/api/v1/requirements", response_model=list[s.RequirementView], dependencies=[Depends(require_key)])
def list_requirements(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db)):
    return db.scalars(select(dbm.Requirement).order_by(dbm.Requirement.id.desc()).limit(limit)).all()


@app.post("/api/v1/objects", response_model=s.ObjectView, status_code=201,
          dependencies=[Depends(require_key)])
def create_obj(value: s.ObjectCreate, db: Session = Depends(dbm.get_db)):
    item = dbm.InfoObject(**value.model_dump())
    db.add(item); db.flush(); log(db, "object", item.id, "create"); db.commit(); db.refresh(item)
    return item


@app.get("/api/v1/objects", response_model=list[s.ObjectView], dependencies=[Depends(require_key)])
def list_objs(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db)):
    return db.scalars(select(dbm.InfoObject).order_by(dbm.InfoObject.id.desc()).limit(limit)).all()


@app.post("/api/v1/measures", response_model=s.MeasureView, status_code=201,
          dependencies=[Depends(require_key)])
def create_measure(value: s.MeasureCreate, db: Session = Depends(dbm.get_db)):
    must_exist(db, dbm.Requirement, value.requirement_id)
    must_exist(db, dbm.InfoObject, value.info_object_id)
    if value.status == "completed" and not (value.evidence_uri and value.reviewed_by):
        raise HTTPException(422, "Для статуса completed нужны evidence_uri и reviewed_by")
    item = dbm.Measure(**value.model_dump())
    db.add(item); db.flush(); log(db, "measure", item.id, "create"); db.commit(); db.refresh(item)
    return item


@app.get("/api/v1/measures", response_model=list[s.MeasureView], dependencies=[Depends(require_key)])
def list_measures(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db)):
    return db.scalars(select(dbm.Measure).order_by(dbm.Measure.id.desc()).limit(limit)).all()


@app.patch("/api/v1/measures/{measure_id}", response_model=s.MeasureView,
           dependencies=[Depends(require_key)])
def update_measure(measure_id: int, value: s.MeasureUpdate, db: Session = Depends(dbm.get_db)):
    item = must_exist(db, dbm.Measure, measure_id)
    for key, val in value.model_dump(exclude_unset=True).items():
        setattr(item, key, val)
    if item.status == "completed" and not (item.evidence_uri and item.reviewed_by):
        raise HTTPException(422, "Для статуса completed нужны evidence_uri и reviewed_by")
    log(db, "measure", item.id, "update"); db.commit(); db.refresh(item)
    return item


@app.get("/api/v1/audit", dependencies=[Depends(require_key)])
def list_audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db)):
    items = db.scalars(select(dbm.AuditEvent).order_by(dbm.AuditEvent.id.desc()).limit(limit)).all()
    return [{"id": x.id, "kind": x.kind, "entity_id": x.entity_id,
             "action": x.action, "created_at": x.created_at} for x in items]
