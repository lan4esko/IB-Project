"""End-to-end lifecycle checks on disposable SQLite test database."""
from test_end_to_end import client


def setup(client):
    oi=client.post('/api/objects',json={'code':'OI-123','name':'Учебный ОИ','classification':'K2'}).json()
    a=client.post('/api/assets',json={'code':'SVT-007','oi_id':oi['id'],'serial_number':'ABC123',
                                      'os_version':'1.7.6','network_segment':'SEG-1'}).json()
    return oi['id'],a['id']


def test_draft_approval_difference_and_immutability(client):
    oi,asset=setup(client)
    custom=client.post('/api/fields',json={'entity_type':'asset','name':'СП','field_type':'text'}).json()
    fid=custom['id']
    client.put(f'/api/values/asset/{asset}/{fid}',json={'value':'2026-СП'})
    doc=client.post('/api/documents?title=Акт%20комплекта',files={'file':('act.pdf',b'%PDF-1.4\nmock')}).json()
    baseline=client.post(f'/api/objects/{oi}/baselines',json={'version':'1.0','notes':'Состав подготовлен для проверки'})
    assert baseline.status_code==201,baseline.text
    b=baseline.json()
    assert b['status']=='draft'
    assert 'snapshot' not in b
    assert client.post(f'/api/objects/{oi}/baselines',json={'version':'1.0','notes':'Повторная версия'}).status_code==409
    bad=client.post(f'/api/objects/{oi}/baselines/{b["id"]}/approve',json={'confirmation':False,'document_id':doc['id'],'approval_note':'Проверено инженером'})
    assert bad.status_code==422
    assert client.post(f'/api/objects/{oi}/baselines/{b["id"]}/approve',json={'confirmation':True,'document_id':doc['id'],'approval_note':'Комплект подтверждён документом'}).status_code==200
    assert client.get(f'/api/objects/{oi}/configuration/compare').json()['matches']
    historical=client.get(f'/api/objects/{oi}/baselines/{b["id"]}').json()
    assert historical['snapshot']['assets'][0]['fields'][str(fid)]['value']=='2026-СП'
    client.patch(f'/api/assets/{asset}',json={'os_version':'1.8','network_segment':'SEG-2'})
    client.put(f'/api/values/asset/{asset}/{fid}',json={'value':'2027-СП'})
    comparison=client.get(f'/api/objects/{oi}/configuration/compare').json()
    assert not comparison['matches']
    changed=comparison['changes']['modified'][0]['fields']
    assert {x['field'] for x in changed}=={'os_version','network_segment','fields'}
    assert historical['snapshot']['assets'][0]['os_version']=='1.7.6'
    added=client.post('/api/assets',json={'code':'SVT-008','oi_id':oi}).json()['id']
    after=client.get(f'/api/objects/{oi}/configuration/compare').json()
    assert after['changes']['added'][0]['id']==added
    client.patch(f'/api/assets/{asset}',json={'oi_id':client.post('/api/objects',json={'code':'OI-124','name':'Other'}).json()['id']})
    after=client.get(f'/api/objects/{oi}/configuration/compare').json()
    assert after['changes']['removed'][0]['id']==asset
    assert client.post(f'/api/objects/{oi}/baselines/{b["id"]}/approve',json={'confirmation':True,'document_id':doc['id'],'approval_note':'Повторно утверждаю'}).status_code==409


def test_stale_draft_must_be_recaptured(client):
    oi,asset=setup(client)
    doc=client.post('/api/documents?title=Акт',files={'file':('act.pdf',b'%PDF-1.4\nmock')}).json()
    baseline=client.post(f'/api/objects/{oi}/baselines',json={'version':'1','notes':'Состав для утверждения'}).json()
    client.patch(f'/api/assets/{asset}',json={'os_version':'1.8'})
    rejected=client.post(f'/api/objects/{oi}/baselines/{baseline["id"]}/approve',json={'confirmation':True,'document_id':doc['id'],'approval_note':'Подтверждаю проверенный состав'})
    assert rejected.status_code==409
    diff=client.get(f'/api/objects/{oi}/configuration/compare?baseline_id={baseline["id"]}').json()
    assert not diff['matches']
    assert client.get(f'/api/objects/{oi}/configuration/compare').status_code==404


def test_change_review_and_cross_oi_guard(client):
    oi,asset=setup(client)
    oi2=client.post('/api/objects',json={'code':'OI-124','name':'Second'}).json()['id']
    data={'asset_id':asset,'change_type':'replacement','summary':'Замена неисправного компьютера',
          'justification':'Отказ системного блока, требуется замена'}
    assert client.post(f'/api/objects/{oi2}/changes',json=data).status_code==422
    resp=client.post(f'/api/objects/{oi}/changes',json=data)
    assert resp.status_code==201,resp.text
    ch=resp.json()
    assert ch['status']=='proposed'
    assert client.patch(f'/api/objects/{oi}/changes/{ch["id"]}',json={'status':'implemented','resolution':'Работы успешно завершены'}).status_code==409
    for status in ('under_review','approved','implemented'):
        resp=client.patch(f'/api/objects/{oi}/changes/{ch["id"]}',json={'status':status,'resolution':'Решение ответственного специалиста'})
        assert resp.status_code==200,resp.text
    assert len(client.get(f'/api/objects/{oi}/changes').json())==1
    assert client.patch(f'/api/objects/{oi2}/changes/{ch["id"]}',json={'status':'cancelled','resolution':'Прекращаем обработку заявки'}).status_code==404
    assert client.patch(f'/api/objects/{oi}/changes/{ch["id"]}',json={'status':'cancelled','resolution':'Прекращаем обработку заявки'}).status_code==409
    assert client.get('/api/audit?entity_type=oi&entity_id='+str(oi)).status_code==200


def test_reader_cannot_approve_snapshot(client):
    from argon2 import PasswordHasher
    from app.db import SessionLocal
    from app.models import User
    from fastapi.testclient import TestClient
    from app.main import app
    oi,asset=setup(client)
    doc=client.post('/api/documents?title=Акт',files={'file':('act.pdf',b'%PDF-1.4\nmock')}).json()
    snap=client.post(f'/api/objects/{oi}/baselines',json={'version':'A','notes':'Тестовый состав для контроля'}).json()
    with SessionLocal.begin() as db:
        db.add(User(username='reader',role='viewer',password_hash=PasswordHasher().hash('reader-password-123')))
    with TestClient(app) as viewer:
        auth=viewer.post('/api/auth/login',json={'username':'reader','password':'reader-password-123'}).json()
        viewer.headers.update({'X-CSRF-Token':auth['csrf']})
        assert viewer.get(f'/api/objects/{oi}/baselines').status_code==200
        assert viewer.get(f'/api/objects/{oi}/configuration/compare?baseline_id={snap["id"]}').status_code==200
        assert viewer.post(f'/api/objects/{oi}/baselines/{snap["id"]}/approve',json={'confirmation':True,'document_id':doc['id'],'approval_note':'Пытаюсь утвердить'}).status_code==403
