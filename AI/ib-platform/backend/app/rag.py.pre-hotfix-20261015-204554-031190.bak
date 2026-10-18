"""Small, ACL-safe text retrieval pilot. NOT an automatic compliance assessor.

Explicit indexing, bounded size, no background scanning, no prompt execution.
Lexical search works offline. Vector embeddings are OPTIONAL and requested
via Ollama /api/embed. ACL checked BEFORE any text is returned to caller.
"""
from __future__ import annotations
import hashlib
import io
import json
import math
import os
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Literal

import httpx
from docx import Document as WordDocument
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import auth, database as dbm, documents

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])
EMBED_MODEL = os.getenv("IB_EMBED_MODEL", "qwen3-embedding:0.6b")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
MAX_SOURCE_BYTES = int(os.getenv("IB_RAG_MAX_SOURCE_MB", "2")) * 1024 * 1024
MAX_PAGES = 20
MAX_CHUNKS = 48
MAX_CHARS = 480
OVERLAP = 70
MAX_CANDIDATES = 2000
_index_lock = threading.Lock()
_words = re.compile(r"[a-zа-яё0-9]{2,}", re.IGNORECASE)


class IndexRequest(BaseModel):
    version: int | None = Field(default=None, ge=1)
    mode: Literal["lexical", "semantic"] = "lexical"


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)
    mode: Literal["lexical", "hybrid"] = "lexical"
    document_ids: list[int] | None = Field(default=None, max_length=100)


def tokens(t: str) -> Counter:
    return Counter(_words.findall(t.casefold()))


def lexical_score(query: Counter, content: str) -> float:
    doc = tokens(content)
    if not query or not doc:
        return 0.0
    covered = sum(min(cnt, doc.get(term, 0)) for term, cnt in query.items())
    return covered / max(1, sum(query.values()))


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x*y for x, y in zip(a, b))
    norma = math.sqrt(sum(x*x for x in a)); normb = math.sqrt(sum(y*y for y in b))
    return dot / (norma*normb) if norma and normb else 0.0


def embed(texts: list[str]) -> list[list[float]]:
    try:
        with httpx.Client(timeout=120, trust_env=False) as client:
            r = client.post(f"{OLLAMA_URL}/api/embed", json={"model": EMBED_MODEL, "input": texts})
            r.raise_for_status()
            vals = r.json()["embeddings"]
        if len(vals) != len(texts) or not vals or any(not isinstance(v, list) or not v for v in vals):
            raise ValueError("Некорректная структура embeddings")
        result = [[float(x) for x in v] for v in vals]
        if any(not all(math.isfinite(x) for x in v) for v in result):
            raise ValueError("Некорректные числа в embeddings")
        return result
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(503, "Embedding-модель Ollama недоступна или вернула ошибку") from exc


def read_original(ver: dbm.DocumentVersion) -> bytes:
    if not documents.KEY_PATTERN.fullmatch(ver.storage_key):
        raise HTTPException(503, "Недопустимое расположение файла")
    path = documents.ROOT / ver.storage_key
    if path.is_symlink() or not path.is_file():
        raise HTTPException(503, "Оригинал документа недоступен")
    if ver.size_bytes > MAX_SOURCE_BYTES:
        raise HTTPException(413, "Документ слишком велик для пилотного индексатора")
    with path.open("rb") as f:
        data = f.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES or len(data) != ver.size_bytes:
        raise HTTPException(413, "Документ превышает лимит")
    if hashlib.sha256(data).hexdigest() != ver.sha256:
        raise HTTPException(503, "Контроль целостности оригинала не пройден")
    return data


def pages_of(ver: dbm.DocumentVersion, data: bytes) -> list[tuple[int | None, str]]:
    ext = Path(ver.filename).suffix.lower()
    if ext in (".txt", ".md", ".csv"):
        try:
            text = data.decode("utf-8-sig", errors="strict")
        except UnicodeError as exc:
            raise HTTPException(422, "Текст должен быть в UTF-8") from exc
        return [(None, text)]
    if ext == ".docx":
        try:
            doc = WordDocument(io.BytesIO(data))
            parts = []
            # Bound decompressed output as well as compressed input.
            for p in doc.paragraphs:
                parts.append(p.text)
                if sum(len(x) for x in parts) > 150_000:
                    raise HTTPException(413, "Слишком много текста в DOCX")
            for table in doc.tables[:20]:
                for row in table.rows[:200]:
                    parts.append(" | ".join(c.text for c in row.cells))
                    if sum(len(x) for x in parts) > 150_000:
                        raise HTTPException(413, "Слишком много текста в DOCX")
            return [(None, "\n".join(parts))]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, "Не удаётся извлечь текст DOCX") from exc
    if ext == ".pdf":
        try:
            pdf = PdfReader(io.BytesIO(data), strict=True)
            if pdf.is_encrypted or len(pdf.pages) > MAX_PAGES:
                raise HTTPException(422, "PDF зашифрован или содержит слишком много страниц")
            result = []
            total = 0
            for idx, p in enumerate(pdf.pages, 1):
                text = p.extract_text() or ""
                total += len(text)
                if total > 150_000:
                    raise HTTPException(413, "Слишком много текста в PDF")
                result.append((idx, text))
            return result
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, "Не удалось извлечь текст PDF") from exc
    raise HTTPException(415, "Индексация поддерживает только TXT, MD, CSV, DOCX и текстовые PDF")


def split_text(text: str) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + MAX_CHARS, len(normalized))
        if end < len(normalized):
            preferred = normalized.rfind(" ", start + MAX_CHARS // 2, end)
            if preferred > start:
                end = preferred
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = max(start + 1, end - OVERLAP)
    return chunks


def prepare(ver: dbm.DocumentVersion) -> list[tuple[int | None, str]]:
    raw = read_original(ver)
    result = []
    for page, text in pages_of(ver, raw):
        for chunk in split_text(text):
            result.append((page, chunk))
            if len(result) > MAX_CHUNKS:
                raise HTTPException(413, "Слишком много фрагментов для пилотного стенда")
    if not result:
        raise HTTPException(422, "Из документа не удалось извлечь текст. Для сканов нужен OCR")
    return result


@router.post("/documents/{document_id}/index")
def index_document(document_id: int, request: IndexRequest,
                   db: Session = Depends(dbm.get_db),
                   actor: auth.Actor = Depends(auth.actor_dependency)):
    auth.require_roles(actor, "admin", "security", "operator")
    doc = documents.require_document(db, document_id, actor, write=True)
    ver = documents.get_version(db, doc, request.version or doc.latest_version)
    if not _index_lock.acquire(blocking=False):
        raise HTTPException(409, "Индексатор занят")
    try:
        parts = prepare(ver)
        embeddings = embed([x[1] for x in parts]) if request.mode == "semantic" else [None]*len(parts)
        # First fully prepare file and vectors, then atomically replace this version's index.
        db.execute(delete(dbm.DocumentChunk).where(dbm.DocumentChunk.document_version_id == ver.id))
        for i, ((page, content), vec) in enumerate(zip(parts, embeddings)):
            db.add(dbm.DocumentChunk(document_id=doc.id, document_version_id=ver.id,
                                    chunk_index=i, page_number=page, content=content,
                                    content_sha256=hashlib.sha256(content.encode()).hexdigest(),
                                    embedding_json=json.dumps(vec) if vec is not None else None,
                                    embedding_model=EMBED_MODEL if vec is not None else None))
        documents.log_event(db, actor, "rag_index", document_id, f"index_v{ver.version}_{request.mode}")
        db.commit()
        return {"document_id": doc.id, "version": ver.version, "indexed_chunks": len(parts),
                "mode": request.mode, "model": EMBED_MODEL if request.mode == "semantic" else None}
    except Exception:
        db.rollback()
        raise
    finally:
        _index_lock.release()


@router.get("/documents/{document_id}/status")
def index_status(document_id: int, db: Session = Depends(dbm.get_db),
                 actor: auth.Actor = Depends(auth.actor_dependency)):
    doc = documents.require_document(db, document_id, actor)
    ver = documents.get_version(db, doc, doc.latest_version)
    chunks = db.scalars(select(dbm.DocumentChunk).where(dbm.DocumentChunk.document_version_id == ver.id)).all()
    return {"document_id": doc.id, "version": ver.version, "indexed": len(chunks) > 0,
            "chunks": len(chunks), "semantic": bool(chunks) and all(c.embedding_json is not None for c in chunks)}


@router.post("/search")
def search(request: SearchRequest, db: Session = Depends(dbm.get_db),
           actor: auth.Actor = Depends(auth.actor_dependency)):
    terms = tokens(request.query)
    if not terms:
        raise HTTPException(422, "Запрос не содержит поисковых слов")
    stmt = (select(dbm.DocumentChunk, dbm.Document, dbm.DocumentVersion)
            .join(dbm.Document, dbm.DocumentChunk.document_id == dbm.Document.id)
            .join(dbm.DocumentVersion, dbm.DocumentChunk.document_version_id == dbm.DocumentVersion.id)
            .where(dbm.Document.latest_version == dbm.DocumentVersion.version))
    if request.document_ids is not None:
        stmt = stmt.where(dbm.Document.id.in_(request.document_ids))
    # For pilot, scan up to MAX_CANDIDATES rows. Larger installations require pgvector + SQL-side ACL.
    candidates = db.execute(stmt.order_by(dbm.DocumentChunk.id.desc()).limit(MAX_CANDIDATES)).all()
    authorized = [(chunk, doc, ver) for chunk, doc, ver in candidates
                  if documents.can_read(db, actor, doc)]
    query_vec = embed([request.query])[0] if request.mode == "hybrid" and any(
        c.embedding_json is not None and c.embedding_model == EMBED_MODEL for c, _, _ in authorized) else None
    results = []
    for chunk, doc, ver in authorized:
        lexical = lexical_score(terms, chunk.content)
        semantic = 0.0
        if query_vec is not None and chunk.embedding_model == EMBED_MODEL and chunk.embedding_json:
            semantic = max(0., cosine(query_vec, json.loads(chunk.embedding_json)))
        score = lexical if request.mode == "lexical" else (0.45*lexical + 0.55*semantic)
        if score <= 0:
            continue
        results.append((score, chunk, doc, ver))
    results.sort(key=lambda item: (-item[0], item[1].id))
    hits = []
    for score, chunk, doc, ver in results[:request.top_k]:
        hits.append({"document_id": doc.id, "title": doc.title, "version": ver.version,
                     "filename": ver.filename, "document_sha256": ver.sha256,
                     "chunk_index": chunk.chunk_index, "page_number": chunk.page_number,
                     "text": chunk.content, "score": round(score, 5),
                     "citation": f"document:{doc.id}:v{ver.version}:chunk:{chunk.chunk_index}"})
    documents.log_event(db, actor, "rag_search", 0, "search")
    db.commit()
    return {"mode": request.mode, "count": len(hits), "hits": hits,
            "note": "Это найденные фрагменты, не юридически подтверждённые выводы"}
