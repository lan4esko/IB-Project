"""Local functional tests use disposable SQLite, not production PostgreSQL."""
import os
import sys
from pathlib import Path
import importlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ["DATABASE_URL"] = "sqlite:////tmp/oi-registry-test-pytest.db"
os.environ["OI_SESSION_SECRET"] = "test-only-secret"
os.environ["OI_DOCUMENT_ROOT"] = "/tmp/oi-registry-pytest-docs"

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from app.db import engine, SessionLocal
from app.models import Base, User
from app.main import app

@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        db.add(User(username="admin", role="admin", password_hash=PasswordHasher().hash("sample-password-123")))
    with TestClient(app) as cli:
        result = cli.post("/api/auth/login", json={"username":"admin", "password":"sample-password-123"})
        assert result.status_code == 200, result.text
        cli.headers.update({"X-CSRF-Token": result.json()["csrf"]})
        yield cli


def test_requires_login_and_rejects_invalid_csrf(client):
    assert TestClient(app).get("/api/assets").status_code == 401
    result=client.post("/api/objects",json={"code":"OI-01","name":"First"},headers={"X-CSRF-Token":"incorrect"})
    assert result.status_code == 403


def test_crud_dynamic_fields_and_evidence_history(client):
    oi=client.post("/api/objects",json={"code":"OI-01","name":"First","openproject_project_id":12})
    assert oi.status_code == 201, oi.text
    oi_id=oi.json()["id"]
    a=client.post("/api/assets",json={"code":"SVT-01","oi_id":oi_id,"serial_number":"SN-123","os_name":"Astra Linux","network_segment":"SEG-01"})
    assert a.status_code == 201, a.text
    aid=a.json()["id"]
    f=client.post("/api/fields",json={"entity_type":"asset","name":"Номер протокола СП","field_type":"text"})
    assert f.status_code == 201, f.text
    fid=f.json()["id"]
    update=client.put(f"/api/values/asset/{aid}/{fid}",json={"value":"СП-102"})
    assert update.status_code == 200, update.text
    doc=client.post("/api/documents?title=Протокол%20СП",files={"file":("report.pdf",b"%PDF-1.4\n%example for registry test", "application/pdf")})
    assert doc.status_code == 201, doc.text
    document_id=doc.json()["id"]
    ev=client.post("/api/evidence",json={"entity_type":"asset","entity_id":aid,"field_key":f"custom:{fid}","document_id":document_id,"locator_type":"page","locator_value":"2"})
    assert ev.status_code==201,ev.text
    assert client.get(f"/api/evidence/asset/{aid}").json()[0]["current_value"] is True
    assert "#page=2" in client.get(f"/api/evidence/asset/{aid}").json()[0]["file_url"]
    assert client.get(f"/api/documents/{document_id}/file").status_code==200
    client.put(f"/api/values/asset/{aid}/{fid}",json={"value":"СП-104"})
    assert client.get(f"/api/evidence/asset/{aid}").json()[0]["current_value"] is False
    history=client.get(f"/api/values/asset/{aid}/{fid}/history").json()
    assert [h["value"] for h in history]==["СП-104","СП-102"]
    listed=client.get('/api/assets?field_id='+str(fid)+'&field_value=СП-104').json()
    assert listed['total']==1
    out=client.get('/api/assets/export.csv?columns=code,serial_number,custom:'+str(fid))
    assert out.status_code==200
    assert 'СП-104' in out.text
    assert client.get('/api/audit').status_code==200


def test_rejects_bad_document_and_duplicates(client):
    bad=client.post('/api/documents?title=Bad',files={'file':('malware.exe',b'MZtest')})
    assert bad.status_code==415
    good=client.post('/api/objects',json={'code':'OI-01','name':'First'})
    assert good.status_code==201
    dup=client.post('/api/objects',json={'code':'OI-01','name':'Second'})
    assert dup.status_code==409,dup.text


def test_select_validation(client):
    oi=client.post('/api/objects',json={'code':'OI-01','name':'First'}).json()
    f=client.post('/api/fields',json={'entity_type':'oi','name':'Класс','field_type':'select','options':['К1','К2']}).json()
    wrong=client.put(f"/api/values/oi/{oi['id']}/{f['id']}",json={'value':'К3'})
    assert wrong.status_code==422
    ok=client.put(f"/api/values/oi/{oi['id']}/{f['id']}",json={'value':'К1'})
    assert ok.status_code==200


def test_local_field_scope_and_viewer_permissions(client):
    oi=client.post('/api/objects',json={'code':'OI-01','name':'First'}).json()
    a1=client.post('/api/assets',json={'code':'SVT-01','oi_id':oi['id']}).json()
    a2=client.post('/api/assets',json={'code':'SVT-02','oi_id':oi['id']}).json()
    f=client.post('/api/fields',json={'entity_type':'asset','scope_entity_id':a1['id'],
                                      'name':'Локальное поле','field_type':'text'}).json()
    assert f['scope_entity_id']==a1['id']
    assert len([x for x in client.get('/api/fields?entity_type=asset&entity_id='+str(a1['id'])).json() if x['id']==f['id']])==1
    assert all(x['id']!=f['id'] for x in client.get('/api/fields?entity_type=asset&entity_id='+str(a2['id'])).json())
    denied=client.put(f"/api/values/asset/{a2['id']}/{f['id']}",json={'value':'123'})
    assert denied.status_code==404
    with SessionLocal.begin() as db:
        db.add(User(username='viewer',role='viewer',password_hash=PasswordHasher().hash('viewer-password-123')))
    from fastapi.testclient import TestClient
    with TestClient(app) as viewer:
        login=viewer.post('/api/auth/login',json={'username':'viewer','password':'viewer-password-123'})
        assert login.status_code==200
        viewer.headers.update({'X-CSRF-Token':login.json()['csrf']})
        assert viewer.get('/api/assets').status_code==200
        assert viewer.post('/api/objects',json={'code':'DENY','name':'Denied'}).status_code==403


def test_export_csv_sanitizes_spreadsheet_formulas(client):
    oi=client.post('/api/objects',json={'code':'OI-01','name':'First'}).json()
    a=client.post('/api/assets',json={'code':'SVT-01','oi_id':oi['id'],'serial_number':'=HYPERLINK("http://invalid")'})
    assert a.status_code==201
    csv=client.get('/api/assets/export.csv?columns=code,serial_number')
    assert csv.status_code==200
    assert "'=HYPERLINK" in csv.text


def test_reverting_value_does_not_revalidate_old_document(client):
    oi=client.post('/api/objects',json={'code':'OI-01','name':'First'}).json()
    asset=client.post('/api/assets',json={'code':'SVT-01','oi_id':oi['id'],'os_version':'1.7.6'}).json()
    doc=client.post('/api/documents?title=Акт',files={'file':('record.pdf',b'%PDF-1.4\n%test')}).json()
    first=client.post('/api/evidence',json={'entity_type':'asset','entity_id':asset['id'],'field_key':'os_version',
        'document_id':doc['id'],'locator_type':'page','locator_value':'3'})
    assert first.status_code==201,first.text
    assert client.get('/api/evidence/asset/'+str(asset['id'])).json()[0]['current_value']
    client.patch('/api/assets/'+str(asset['id']),json={'os_version':'1.8'})
    assert not client.get('/api/evidence/asset/'+str(asset['id'])).json()[0]['current_value']
    client.patch('/api/assets/'+str(asset['id']),json={'os_version':'1.7.6'})
    assert not client.get('/api/evidence/asset/'+str(asset['id'])).json()[0]['current_value']
