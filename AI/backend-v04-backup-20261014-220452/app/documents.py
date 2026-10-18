"""Small-file document vault for the development stand.

Private, versioned, ACL-filtered binary storage. Not yet a parser, RAG, DLP or
malware scanning service. Files are stored only in a separate persistent volume.
"""
import hashlib
import os
import re
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auth, database as dbm

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
ROOT = Path(os.getenv("IB_DOCUMENTS_ROOT", "/data/documents"))
MAX_UPLOAD_BYTES = int(os.getenv("IB_MAX_UPLOAD_MB", "10")) * 1024 * 1024
CHUNK = 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv", ".odt", ".ods", ".odp"}
KEY_PATTERN = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{32}$")


class GrantInput(BaseModel):
    permission: str = Field(pattern=r"^(read|write)$")


def log_event(db: Session, actor: auth.Actor, kind: str, entity_id: int, action: str):
    db.add(dbm.AuditEvent(kind=kind, entity_id=entity_id, action=action, actor_user_id=actor.id))


def normalize_filename(filename: str | None) -> str:
    # Don't allow user-supplied paths, control characters, or executable formats.
    if not filename or len(filename) > 180 or filename in (".", ".."):
        raise HTTPException(422, "Недопустимое имя файла")
    if any(x in filename for x in ('/', '\\', '\x00')) or any(ord(x) < 32 or ord(x) == 127 for x in filename):
        raise HTTPException(422, "Имя файла не должно содержать путь или управляющие символы")
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Неподдерживаемое расширение файла")
    return filename


def can_read(db: Session, actor: auth.Actor, doc: dbm.Document, write: bool = False) -> bool:
    if actor.role == "admin":
        return True
    # Linked object ACL must ALSO permit the operation; doc grants cannot override it.
    if doc.info_object_id is not None and not auth.may_access_object(db, actor, doc.info_object_id, write=write):
        return False
    if actor.id == doc.created_by:
        return True
    g = db.scalar(select(dbm.DocumentGrant).where(dbm.DocumentGrant.document_id == doc.id,
                                                  dbm.DocumentGrant.user_id == actor.id))
    return g is not None and (g.permission == "write" or not write)


def require_document(db: Session, doc_id: int, actor: auth.Actor, write: bool = False) -> dbm.Document:
    doc = db.get(dbm.Document, doc_id)
    if doc is None or not can_read(db, actor, doc, write=write):
        # Hide existence and metadata of inaccessible documents.
        raise HTTPException(404, "Документ не найден")
    return doc


def doc_view(doc: dbm.Document):
    return {"id": doc.id, "title": doc.title, "created_by": doc.created_by,
            "info_object_id": doc.info_object_id, "latest_version": doc.latest_version,
            "created_at": doc.created_at}


def ver_view(item: dbm.DocumentVersion):
    return {"id": item.id, "document_id": item.document_id, "version": item.version,
            "filename": item.filename, "content_type": item.content_type,
            "size_bytes": item.size_bytes, "sha256": item.sha256,
            "uploaded_by": item.uploaded_by, "created_at": item.created_at}


async def persist(upload: UploadFile):
    filename = normalize_filename(upload.filename)
    if MAX_UPLOAD_BYTES < 1:
        raise HTTPException(503, "Некорректный лимит загрузки")
    root = ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)
    key_hex = uuid.uuid4().hex
    storage_key = f"{key_hex[:2]}/{key_hex}"
    target = root / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    digest = hashlib.sha256()
    size = 0
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".incoming-", dir=str(root))
        with os.fdopen(fd, "wb") as handle:
            os.chmod(tmp_path, 0o600)
            while data := await upload.read(CHUNK):
                size += len(data)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Файл превышает лимит загрузки")
                digest.update(data)
                handle.write(data)
            if size == 0:
                raise HTTPException(422, "Пустой файл")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
        tmp_path = None
        return filename, (upload.content_type or "application/octet-stream")[:150], size, digest.hexdigest(), storage_key
    finally:
        await upload.close()
        if tmp_path is not None:
            Path(tmp_path).unlink(missing_ok=True)


def erase_blob(storage_key: str):
    if KEY_PATTERN.fullmatch(storage_key):
        (ROOT / storage_key).unlink(missing_ok=True)


def get_version(db: Session, doc: dbm.Document, number: int):
    ver = db.scalar(select(dbm.DocumentVersion).where(dbm.DocumentVersion.document_id == doc.id,
                                                        dbm.DocumentVersion.version == number))
    if ver is None:
        raise HTTPException(404, "Версия документа не найдена")
    return ver


@router.post("", status_code=201)
async def create_document(title: str = Form(..., min_length=1, max_length=300),
                          file: UploadFile = File(...), info_object_id: int | None = Form(None),
                          db: Session = Depends(dbm.get_db), actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "security", "operator")
    if not title.strip():
        raise HTTPException(422, "Пустое название документа")
    if info_object_id is not None:
        if db.get(dbm.InfoObject, info_object_id) is None:
            raise HTTPException(404, "Объект не найден")
        if not auth.may_access_object(db, actor, info_object_id, write=True):
            raise HTTPException(403, "Нет права записи в объект")
    filename, mime, size, digest, storage_key = await persist(file)
    try:
        doc = dbm.Document(title=title.strip(), created_by=actor.id,
                           info_object_id=info_object_id, latest_version=1)
        db.add(doc)
        db.flush()
        version = dbm.DocumentVersion(document_id=doc.id, version=1, filename=filename,
                                      content_type=mime, size_bytes=size, sha256=digest,
                                      storage_key=storage_key, uploaded_by=actor.id)
        db.add(version)
        log_event(db, actor, "document", doc.id, "create")
        db.commit()
        db.refresh(doc)
        return doc_view(doc)
    except Exception:
        db.rollback()
        erase_blob(storage_key)
        raise


@router.get("")
def list_documents(limit: int = Query(100, ge=1, le=500), db: Session = Depends(dbm.get_db),
                   actor: auth.Actor = Depends(auth.actor_dependency)):
    # Pilot database-scope query; verify ACL again before returning metadata.
    if actor.role == "admin":
        stmt = select(dbm.Document)
    else:
        stmt = select(dbm.Document).where(
            (dbm.Document.created_by == actor.id) |
            dbm.Document.id.in_(select(dbm.DocumentGrant.document_id).where(dbm.DocumentGrant.user_id == actor.id)))
    docs = db.scalars(stmt.order_by(dbm.Document.id.desc()).limit(limit)).all()
    return [doc_view(doc) for doc in docs if can_read(db, actor, doc)]


@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(dbm.get_db),
                 actor: auth.Actor = Depends(auth.actor_dependency)):
    return doc_view(require_document(db, document_id, actor))


@router.get("/{document_id}/versions")
def list_versions(document_id: int, db: Session = Depends(dbm.get_db),
                  actor: auth.Actor = Depends(auth.actor_dependency)):
    doc = require_document(db, document_id, actor)
    versions = db.scalars(select(dbm.DocumentVersion).where(
        dbm.DocumentVersion.document_id == doc.id).order_by(dbm.DocumentVersion.version)).all()
    return [ver_view(x) for x in versions]


@router.post("/{document_id}/versions", status_code=201)
async def upload_version(document_id: int, file: UploadFile = File(...),
                         db: Session = Depends(dbm.get_db), actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "security", "operator")
    doc = require_document(db, document_id, actor, write=True)
    filename, mime, size, digest, storage_key = await persist(file)
    try:
        version_num = doc.latest_version + 1
        doc.latest_version = version_num
        ver = dbm.DocumentVersion(document_id=doc.id, version=version_num, filename=filename,
                                  content_type=mime, size_bytes=size, sha256=digest,
                                  storage_key=storage_key, uploaded_by=actor.id)
        db.add(ver)
        log_event(db, actor, "document", doc.id, "new_version")
        db.commit()
        db.refresh(ver)
        return ver_view(ver)
    except IntegrityError as exc:
        db.rollback()
        erase_blob(storage_key)
        raise HTTPException(409, "Конфликт параллельной загрузки версии, повторите запрос") from exc
    except Exception:
        db.rollback()
        erase_blob(storage_key)
        raise


def download_response(db: Session, document_id: int, version: int | None, actor: auth.Actor):
    doc = require_document(db, document_id, actor)
    ver = get_version(db, doc, version if version is not None else doc.latest_version)
    if not KEY_PATTERN.fullmatch(ver.storage_key):
        raise HTTPException(503, "Недопустимое расположение файла")
    path = ROOT / ver.storage_key
    if not path.is_file() or path.is_symlink():
        raise HTTPException(503, "Оригинал документа недоступен")
    # Check file integrity before delivery; files in this pilot are capped at 10 MB.
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            digest.update(block)
    if digest.hexdigest() != ver.sha256:
        raise HTTPException(503, "Контроль целостности не пройден")
    log_event(db, actor, "document", doc.id, f"download_v{ver.version}")
    db.commit()
    return FileResponse(path, filename=ver.filename, media_type="application/octet-stream",
                        content_disposition_type="attachment",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                                 "X-Document-SHA256": ver.sha256})


@router.get("/{document_id}/download")
def download_latest(document_id: int, db: Session = Depends(dbm.get_db),
                    actor: auth.Actor = Depends(auth.actor_dependency)):
    return download_response(db, document_id, None, actor)


@router.get("/{document_id}/versions/{version}/download")
def download_version(document_id: int, version: int, db: Session = Depends(dbm.get_db),
                     actor: auth.Actor = Depends(auth.actor_dependency)):
    return download_response(db, document_id, version, actor)


@router.get("/{document_id}/acl")
def list_acl(document_id: int, db: Session = Depends(dbm.get_db),
             actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin")
    doc = db.get(dbm.Document, document_id)
    if doc is None:
        raise HTTPException(404, "Документ не найден")
    grants = db.scalars(select(dbm.DocumentGrant).where(dbm.DocumentGrant.document_id == doc.id)).all()
    return [{"user_id": x.user_id, "permission": x.permission} for x in grants]


@router.put("/{document_id}/acl/{user_id}")
def put_acl(document_id: int, user_id: int, val: GrantInput,
            db: Session = Depends(dbm.get_db), actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin")
    doc = db.get(dbm.Document, document_id)
    if doc is None or db.get(dbm.User, user_id) is None:
        raise HTTPException(404, "Документ или пользователь не найден")
    grant = db.scalar(select(dbm.DocumentGrant).where(dbm.DocumentGrant.document_id == doc.id,
                                                       dbm.DocumentGrant.user_id == user_id))
    if grant is None:
        grant = dbm.DocumentGrant(document_id=doc.id, user_id=user_id, permission=val.permission)
        db.add(grant)
    else:
        grant.permission = val.permission
    log_event(db, actor, "document_acl", doc.id, "grant")
    db.commit()
    return {"document_id": doc.id, "user_id": user_id, "permission": val.permission}


@router.delete("/{document_id}/acl/{user_id}", status_code=204)
def revoke_acl(document_id: int, user_id: int, db: Session = Depends(dbm.get_db),
               actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin")
    grant = db.scalar(select(dbm.DocumentGrant).where(dbm.DocumentGrant.document_id == document_id,
                                                       dbm.DocumentGrant.user_id == user_id))
    if grant is None:
        raise HTTPException(404, "Разрешение не найдено")
    db.delete(grant)
    log_event(db, actor, "document_acl", document_id, "revoke")
    db.commit()
    return None
