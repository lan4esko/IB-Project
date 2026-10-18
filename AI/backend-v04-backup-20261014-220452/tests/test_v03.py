import os
import tempfile
from pathlib import Path

# Set all settings before importing app modules.
TEMP = tempfile.TemporaryDirectory()
os.environ['IB_DATABASE_URL'] = 'sqlite:///' + str(Path(TEMP.name) / 'auth-test.db')
os.environ['IB_PLATFORM_API_KEY'] = 'legacy-testing-secret'
os.environ['IB_ALLOW_LEGACY_API_KEY'] = 'false'

from fastapi.testclient import TestClient
from app import database as dbm, auth
from app.main import app


def test_v03_auth_roles_acl():
    with TestClient(app) as client:
        dbm.Base.metadata.create_all(dbm.engine)
        with dbm.SessionLocal() as session:
            session.add(dbm.User(username='admin', role='admin', is_active=True,
                                 password_hash=auth.hash_password('TestAdminPassword123!')))
            session.commit()
        assert client.get('/health/live').json()['version'] == '0.4.0'
        assert client.get('/api/v1/models/catalog').status_code == 401
        assert client.get('/api/v1/models/catalog', headers={'X-API-Key': 'legacy-testing-secret'}).status_code == 401
        assert client.post('/api/v1/auth/login', json={'username':'admin','password':'bad'}).status_code == 401
        resp = client.post('/api/v1/auth/login', json={'username':'admin','password':'TestAdminPassword123!'})
        assert resp.status_code == 200, resp.text
        admin = {'Authorization':'Bearer '+resp.json()['access_token']}
        assert client.get('/api/v1/auth/me',headers=admin).json()['role'] == 'admin'
        assert client.get('/api/v1/models/catalog',headers=admin).status_code == 200
        a = client.post('/api/v1/acts',headers=admin,json={'code':'T-1','title':'Regulation','revision':'1'})
        assert a.status_code == 201, a.text
        req = client.post('/api/v1/requirements',headers=admin,json={'act_id':a.json()['id'],'clause':'1','text':'control'})
        assert req.status_code == 201, req.text
        o = client.post('/api/v1/objects',headers=admin,json={'name':'Secret test object'})
        assert o.status_code == 201, o.text
        oid=o.json()['id']
        m = client.post('/api/v1/measures',headers=admin,json={'requirement_id':req.json()['id'],'info_object_id':oid,'action':'Do X','owner':'Test'})
        assert m.status_code == 201, m.text
        u = client.post('/api/v1/users',headers=admin,json={'username':'worker','password':'TestWorkerPassword123!','role':'operator'})
        assert u.status_code == 201, u.text
        uid=u.json()['id']
        assert 'password_hash' not in u.json()
        r = client.post('/api/v1/auth/login',json={'username':'worker','password':'TestWorkerPassword123!'})
        assert r.status_code==200
        worker={'Authorization':'Bearer '+r.json()['access_token']}
        assert client.get('/api/v1/users',headers=worker).status_code==403
        assert client.get('/api/v1/objects',headers=worker).json()==[]
        assert client.get('/api/v1/measures',headers=worker).json()==[]
        assert client.get('/api/v1/objects/'+str(oid),headers=worker).status_code==404
        assert client.post('/api/v1/measures',headers=worker,json={'requirement_id':req.json()['id'],'info_object_id':oid,'action':'No','owner':'worker'}).status_code == 403
        grant = client.put(f'/api/v1/objects/{oid}/acl/{uid}',headers=admin,json={'permission':'read'})
        assert grant.status_code == 200, grant.text
        assert len(client.get('/api/v1/objects',headers=worker).json())==1
        assert len(client.get('/api/v1/measures',headers=worker).json())==1
        assert client.patch(f'/api/v1/measures/{m.json()["id"]}',headers=worker,json={'action':'Bad change'}).status_code==403
        grant = client.put(f'/api/v1/objects/{oid}/acl/{uid}',headers=admin,json={'permission':'write'})
        assert grant.status_code==200
        assert client.patch(f'/api/v1/measures/{m.json()["id"]}',headers=worker,json={'action':'Good change'}).status_code==200
        assert client.delete(f'/api/v1/objects/{oid}/acl/{uid}',headers=admin).status_code==204
        assert client.get('/api/v1/objects',headers=worker).json()==[]
        assert client.post('/api/v1/auth/logout',headers=worker).status_code==204
        assert client.get('/api/v1/auth/me',headers=worker).status_code==401
        # Disabling a user blocks active sessions immediately.
        r=client.post('/api/v1/auth/login',json={'username':'worker','password':'TestWorkerPassword123!'})
        worker2={'Authorization':'Bearer '+r.json()['access_token']}
        assert client.patch(f'/api/v1/users/{uid}',headers=admin,json={'is_active':False}).status_code==200
        assert client.get('/api/v1/auth/me',headers=worker2).status_code==401
        assert client.patch('/api/v1/users/1',headers=admin,json={'is_active':False}).status_code==409


def test_no_null_user_role():
    from app.main import app
    with TestClient(app) as client:
        # no need to reinitialize DB after first test
        token = client.post('/api/v1/auth/login',json={'username':'admin','password':'TestAdminPassword123!'}).json()['access_token']
        header={'Authorization':'Bearer '+token}
        assert client.patch('/api/v1/users/2',headers=header,json={'role':None}).status_code==422
