from fastapi.testclient import TestClient
from app.main import app

def test_v02_live_and_ready():
    with TestClient(app) as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["version"] == "0.2.0"
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["database"] == "sqlite"
