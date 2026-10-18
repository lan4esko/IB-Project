import hashlib
import os
import tempfile
from pathlib import Path

TMP = tempfile.TemporaryDirectory()
os.environ['IB_DATABASE_URL'] = 'sqlite:///' + str(Path(TMP.name) / 'documents.db')
os.environ['IB_ALLOW_LEGACY_API_KEY'] = 'false'
os.environ['IB_DOCUMENTS_ROOT'] = str(Path(TMP.name) / 'blobs')
os.environ['IB_MAX_UPLOAD_MB'] = '1'

from fastapi.testclient import TestClient
from sqlalchemy import select
from app import auth, database as dbm
from app import documents
from app.main import app


def test_documents_access_versions_and_integrity():
    # This test can run alone or with the v0.3 compatibility tests.
    documents.ROOT = Path(TMP.name) / 'blobs'
    documents.MAX_UPLOAD_BYTES = 1024 * 1024
    with TestClient(app) as c:
        dbm.Base.metadata.create_all(dbm.engine)
        with dbm.SessionLocal() as db:
            for name, role in [('documentadmin', 'admin'), ('docreader', 'viewer'), ('docoperator', 'operator')]:
                db.add(dbm.User(username=name, role=role, is_active=True,
                                password_hash=auth.hash_password('TestPassword123!abcd')))
            db.commit()
        def login(name):
            response = c.post('/api/v1/auth/login', json={'username': name, 'password': 'TestPassword123!abcd'})
            assert response.status_code == 200, response.text
            return {'Authorization': 'Bearer ' + response.json()['access_token']}
        admin, reader, operator = login('documentadmin'), login('docreader'), login('docoperator')

        assert c.get('/api/v1/documents').status_code == 401
        r = c.post('/api/v1/documents', headers=admin, data={'title':'Test file'},
                   files={'file': ('policy.md', b'First revision', 'text/markdown')})
        assert r.status_code == 201, r.text
        did = r.json()['id']
        assert r.json()['latest_version'] == 1
        assert c.get('/api/v1/documents', headers=reader).json() == []
        assert c.get(f'/api/v1/documents/{did}', headers=reader).status_code == 404
        assert c.get(f'/api/v1/documents/{did}/download', headers=reader).status_code == 404
        assert c.post('/api/v1/documents', headers=reader, data={'title':'No'},
                      files={'file': ('ok.md', b'no')}).status_code == 403
        with dbm.SessionLocal() as db:
            reader_id = db.scalar(select(dbm.User).where(dbm.User.username == 'docreader')).id
        grant = c.put(f'/api/v1/documents/{did}/acl/{reader_id}', headers=admin, json={'permission': 'read'})
        assert grant.status_code == 200, grant.text
        assert len(c.get('/api/v1/documents', headers=reader).json()) == 1
        r = c.get(f'/api/v1/documents/{did}/download', headers=reader)
        assert r.status_code == 200
        assert r.content == b'First revision'
        assert r.headers['x-content-type-options'] == 'nosniff'
        assert r.headers['x-document-sha256'] == hashlib.sha256(b'First revision').hexdigest()
        assert c.post(f'/api/v1/documents/{did}/versions', headers=reader,
                      files={'file':('policy.md',b'intrusion')}).status_code == 403
        v = c.post(f'/api/v1/documents/{did}/versions', headers=admin,
                   files={'file':('policy.md', b'Second revision')})
        assert v.status_code == 201, v.text
        assert v.json()['version'] == 2
        assert c.get(f'/api/v1/documents/{did}/download', headers=reader).content == b'Second revision'
        assert c.get(f'/api/v1/documents/{did}/versions/1/download', headers=reader).content == b'First revision'
        assert len(c.get(f'/api/v1/documents/{did}/versions', headers=reader).json()) == 2
        assert c.delete(f'/api/v1/documents/{did}/acl/{reader_id}', headers=admin).status_code == 204
        assert c.get(f'/api/v1/documents/{did}', headers=reader).status_code == 404

        for filename, data, code in [('bad.exe', b'data', 415), ('../bad.md', b'data', 422),
                                     ('empty.md', b'', 422), ('too-big.md', b'a' * (1024 * 1024 + 1), 413)]:
            r = c.post('/api/v1/documents', headers=admin, data={'title':'invalid'},
                       files={'file': (filename, data)})
            assert r.status_code == code, (filename, r.status_code, r.text)

        # Correctly scoped object ACL is required on top of document access.
        obj = c.post('/api/v1/objects', headers=admin, json={'name':'Object for document test'})
        assert obj.status_code == 201
        oid = obj.json()['id']
        d = c.post('/api/v1/documents', headers=admin,
                   data={'title':'Linked test', 'info_object_id':str(oid)},
                   files={'file':('link.txt',b'Linked')})
        assert d.status_code == 201, d.text
        linked = d.json()['id']
        c.put(f'/api/v1/documents/{linked}/acl/{reader_id}', headers=admin, json={'permission':'read'})
        assert c.get(f'/api/v1/documents/{linked}', headers=reader).status_code == 404
        c.put(f'/api/v1/objects/{oid}/acl/{reader_id}', headers=admin, json={'permission':'read'})
        assert c.get(f'/api/v1/documents/{linked}', headers=reader).status_code == 200
        assert c.post(f'/api/v1/documents/{linked}/versions', headers=reader,
                      files={'file':('link.txt',b'overwrite')}).status_code == 403
        c.delete(f'/api/v1/objects/{oid}/acl/{reader_id}', headers=admin)
        assert c.get(f'/api/v1/documents/{linked}', headers=reader).status_code == 404

        # Tampering with an on-disk original is detected and refused.
        with dbm.SessionLocal() as db:
            ver = db.scalar(select(dbm.DocumentVersion).where(dbm.DocumentVersion.document_id == did,
                                                                          dbm.DocumentVersion.version == 2))
            path = documents.ROOT / ver.storage_key
        path.write_bytes(b'evil overwrite')
        assert c.get(f'/api/v1/documents/{did}/download', headers=admin).status_code == 503


def test_no_legacy_key_bypass():
    with TestClient(app) as c:
        assert c.get('/api/v1/documents', headers={'X-API-Key': 'secret'}).status_code == 401
