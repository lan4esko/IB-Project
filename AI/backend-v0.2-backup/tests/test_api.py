import os
import tempfile
from pathlib import Path

# Set env before importing application modules.
TEMP = tempfile.TemporaryDirectory()
os.environ["IB_DATABASE_URL"] = "sqlite:///" + str(Path(TEMP.name) / "test.db")
os.environ["IB_PLATFORM_API_KEY"] = "test-api-secret"

from fastapi.testclient import TestClient
from app.main import app

HEADERS = {"X-API-Key": "test-api-secret"}


def test_health_and_auth():
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/api/v1/models/catalog").status_code == 401
        r = client.get("/api/v1/models/catalog", headers=HEADERS)
        assert r.status_code == 200
        assert any(m["tag"] == "gpt-oss:20b" for m in r.json()["models"])


def test_revisions_objects_measures_and_audit():
    with TestClient(app) as client:
        a = client.post("/api/v1/acts", headers=HEADERS,
                        json={"code": "TRAIN-1", "title": "Учебный акт", "revision": "2026"})
        assert a.status_code == 201, a.text
        act_id = a.json()["id"]
        dup = client.post("/api/v1/acts", headers=HEADERS,
                          json={"code": "TRAIN-1", "title": "Учебный акт", "revision": "2026"})
        assert dup.status_code == 409
        a2 = client.post("/api/v1/acts", headers=HEADERS,
                         json={"code": "TRAIN-1", "title": "Учебный акт", "revision": "2027"})
        assert a2.status_code == 201
        r = client.post("/api/v1/requirements", headers=HEADERS,
                        json={"act_id": act_id, "clause": "1.1", "text": "Учебная проверка"})
        assert r.status_code == 201, r.text
        req_id = r.json()["id"]
        o = client.post("/api/v1/objects", headers=HEADERS,
                        json={"name": "Лабораторный объект", "stage": "planning"})
        assert o.status_code == 201, o.text
        obj_id = o.json()["id"]
        m = client.post("/api/v1/measures", headers=HEADERS,
                        json={"requirement_id": req_id, "info_object_id": obj_id,
                              "action": "Провести контроль", "owner": "Отдел ИБ"})
        assert m.status_code == 201, m.text
        mid = m.json()["id"]
        bad = client.patch(f"/api/v1/measures/{mid}", headers=HEADERS,
                           json={"status": "completed"})
        assert bad.status_code == 422
        ok = client.patch(f"/api/v1/measures/{mid}", headers=HEADERS,
                          json={"status": "completed", "evidence_uri": "urn:demo:evidence:1", "reviewed_by": "tester"})
        assert ok.status_code == 200, ok.text
        assert client.get("/api/v1/acts", headers=HEADERS).status_code == 200
        assert client.get("/api/v1/requirements", headers=HEADERS).status_code == 200
        assert client.get("/api/v1/objects", headers=HEADERS).status_code == 200
        assert client.get("/api/v1/measures", headers=HEADERS).status_code == 200
        assert len(client.get("/api/v1/audit", headers=HEADERS).json()) >= 5


def test_openproject_unconfigured():
    with TestClient(app) as client:
        status = client.get("/api/v1/integrations/openproject/status", headers=HEADERS)
        assert status.status_code == 200
        assert status.json()["status"] in ("not_configured", "reachable", "unreachable")
