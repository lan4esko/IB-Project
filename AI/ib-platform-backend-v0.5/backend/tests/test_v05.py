import os
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import select
from app import auth, database as dbm, documents, rag
from app.main import app


def test_index_acl_revisions_integrity(tmp_path, monkeypatch):
    monkeypatch.setattr(documents, "ROOT", tmp_path / "files")
    monkeypatch.setattr(rag, "MAX_SOURCE_BYTES", 1024*1024)
    dbm.Base.metadata.create_all(dbm.engine)
    with dbm.SessionLocal() as db:
        for name, role in (("ragadmin", "admin"), ("ragviewer", "viewer")):
            if db.scalar(select(dbm.User).where(dbm.User.username == name)) is None:
                db.add(dbm.User(username=name, role=role, is_active=True,
                    password_hash=auth.hash_password("DemoPassword123!hello")))
        db.commit()
    with TestClient(app) as c:
        def headers(name):
            res = c.post("/api/v1/auth/login", json={"username":name,"password":"DemoPassword123!hello"})
            assert res.status_code == 200, res.text
            return {"Authorization": "Bearer " + res.json()["access_token"]}
        admin = headers("ragadmin"); viewer = headers("ragviewer")
        doc1 = c.post("/api/v1/documents",headers=admin,data={"title":"Private policy"},
             files={"file": ("order.md", "Серверы проверяются каждый месяц. Ответственный администратор ИБ.".encode(),"text/markdown")})
        assert doc1.status_code == 201, doc1.text
        docid = doc1.json()["id"]
        r = c.post(f"/api/v1/rag/documents/{docid}/index", headers=viewer,json={})
        assert r.status_code in (403,404)
        r = c.post(f"/api/v1/rag/documents/{docid}/index", headers=admin,json={})
        assert r.status_code == 200, r.text
        assert r.json()["indexed_chunks"] >= 1
        query={"query":"Серверы проверяются ежемесячно", "top_k":5}
        r=c.post("/api/v1/rag/search",headers=admin,json=query)
        assert r.status_code==200 and r.json()["count"]>=1, r.text
        assert r.json()["hits"][0]["document_id"] == docid
        assert r.json()["hits"][0]["citation"].startswith(f"document:{docid}:v1")
        assert c.post("/api/v1/rag/search",headers=viewer,json=query).json()["count"]==0
        with dbm.SessionLocal() as db:
            vid=db.scalar(select(dbm.User).where(dbm.User.username=="ragviewer")).id
        assert c.put(f"/api/v1/documents/{docid}/acl/{vid}",headers=admin,json={"permission":"read"}).status_code==200
        assert c.post("/api/v1/rag/search",headers=viewer,json=query).json()["count"]>=1
        assert c.delete(f"/api/v1/documents/{docid}/acl/{vid}",headers=admin).status_code==204
        assert c.post("/api/v1/rag/search",headers=viewer,json=query).json()["count"]==0
        # New latest document version invalidates all old-version search results automatically.
        new=c.post(f"/api/v1/documents/{docid}/versions",headers=admin,
            files={"file":("order.md", "Новая редакция касается только архивов.".encode())})
        assert new.status_code == 201, new.text
        assert c.post("/api/v1/rag/search",headers=admin,json=query).json()["count"]==0
        assert c.post(f"/api/v1/rag/documents/{docid}/index", headers=admin,json={}).status_code==200
        assert c.post("/api/v1/rag/search",headers=admin,json={"query":"архивов"}).json()["count"]>=1
        # Vector indexing and hybrid scoring without a real Ollama call during unit tests.
        monkeypatch.setattr(rag, "embed", lambda texts: [[1.0, 0.0] for _ in texts])
        indexed = c.post(f"/api/v1/rag/documents/{docid}/index",headers=admin,
                         json={"mode":"semantic"})
        assert indexed.status_code == 200, indexed.text
        assert c.get(f"/api/v1/rag/documents/{docid}/status",headers=admin).json()["semantic"] is True
        hybrid = c.post("/api/v1/rag/search",headers=admin,
                        json={"query":"архивов", "mode":"hybrid"})
        assert hybrid.status_code == 200 and hybrid.json()["count"] >= 1
        # Integrity failures refuse indexing.
        with dbm.SessionLocal() as db:
            ver=db.scalar(select(dbm.DocumentVersion).where(dbm.DocumentVersion.document_id==docid,
                    dbm.DocumentVersion.version==2))
            (documents.ROOT/ver.storage_key).write_bytes(b"changed")
        assert c.post(f"/api/v1/rag/documents/{docid}/index", headers=admin,json={}).status_code in (413,503)


def test_retrieval_not_open_without_auth():
    with TestClient(app) as c:
        assert c.post("/api/v1/rag/search", json={"query":"Документ"}).status_code==401


def test_chunk_math_and_errors():
    assert rag.cosine([1,0], [0,1]) == 0
    assert rag.cosine([1,0], [1,0]) == 1
    assert rag.lexical_score(rag.tokens("защита данных"), "защита данных") == 1
    assert rag.split_text(" ") == []
