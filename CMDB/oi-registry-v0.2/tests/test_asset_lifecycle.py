"""Inventory/repairs/inspection invariants on disposable DB."""
from test_end_to_end import client


def create(client):
    oi=client.post('/api/objects',json={'code':'OI-100','name':'Комплекс СВТ'}).json()
    a=client.post('/api/assets',json={'code':'SVT-100','oi_id':oi['id'],'hostname':'ws-01',
                                      'domain_name':'example.test','seal_state':'sealed'}).json()
    return oi['id'],a['id']


def test_asset_parts_shared_mfp_security_snapshot_and_history(client):
    oi,asset=create(client)
    doc=client.post('/api/documents?title=Тестовый%20протокол',files={'file':('report.pdf',b'%PDF-1.4\n%test')}).json()['id']
    p=client.post(f'/api/assets/{asset}/components',json={'kind':'disk','serial_number':'DISK-123','manufacturer':'T','document_id':doc})
    assert p.status_code==201,p.text
    c=p.json()['id']
    m=client.post(f'/api/objects/{oi}/peripherals',json={'name':'МФУ №1','serial_number':'MFP-001','ip_address':'10.1.1.17'})
    assert m.status_code==201,m.text
    m_id=m.json()['id']
    a2=client.post('/api/assets',json={'code':'SVT-101','oi_id':oi}).json()['id']
    link=client.post(f'/api/assets/{asset}/peripherals',json={'peripheral_id':m_id,'reason':'Разрешено по заявке'})
    assert link.status_code==201,link.text
    assert client.post(f'/api/assets/{a2}/peripherals',json={'peripheral_id':m_id,'reason':'Разрешено по заявке'}).status_code==201
    assert client.post(f'/api/assets/{asset}/peripherals',json={'peripheral_id':m_id,'reason':'Дубль разрешения'}).status_code==409
    t=client.post(f'/api/assets/{asset}/security-tools',json={'name':'Средство защиты','version':'2.4','expires_on':'2026-12-31'})
    assert t.status_code==201,t.text
    snap=client.post(f'/api/objects/{oi}/baselines',json={'version':'v1','notes':'Проверенная опись комплектов'}).json()
    baseline=client.get(f'/api/objects/{oi}/baselines/{snap["id"]}').json()['snapshot']
    target=next(x for x in baseline['assets'] if x['id']==asset)
    assert target['hostname']=='ws-01'
    assert target['components'][0]['serial_number']=='DISK-123'
    assert target['peripherals'][0]['serial_number']=='MFP-001'
    assert target['security_tools'][0]['name']=='Средство защиты'
    assert client.post(f'/api/assets/{asset}/components/{c}/remove',json={'reason':'Замена вышедшего из строя диска'}).status_code==200
    delta=client.get(f'/api/objects/{oi}/configuration/compare?baseline_id={snap["id"]}').json()
    assert 'components' in {x['field'] for y in delta['changes']['modified'] for x in y['fields']}
    assert len(client.get(f'/api/assets/{asset}/components').json())==1
    assert len(client.get(f'/api/assets/{asset}/components?current_only=true').json())==0
    other=client.post('/api/objects',json={'code':'OI-200','name':'Чужой ОИ'}).json()['id']
    foreign=client.post(f'/api/objects/{other}/peripherals',json={'name':'Чужое МФУ','serial_number':'X1'}).json()['id']
    assert client.post(f'/api/assets/{asset}/peripherals',json={'peripheral_id':foreign,'reason':'Попытка доступа'}).status_code==422


def test_requests_work_seal_journal_and_inspections(client):
    oi,asset=create(client)
    req=client.post(f'/api/assets/{asset}/requests',json={'reporter':'Сотрудник 1','subject':'Не запускается рабочая станция',
        'fault_description':'Не работает загрузка операционной системы'})
    assert req.status_code==201,req.text
    rid=req.json()['id']
    assert client.post(f'/api/assets/{asset}/requests/{rid}/close',json={'resolution':'Ремонт окончен'}).status_code==409
    base={'service_request_id':rid,'performer':'Инженер 1','work_type':'repair',
          'actions':'Проверен блок питания и заменён диск','result':'Операционная система запускается',
          'seal_state_after':'unsealed_after_repair'}
    assert client.post(f'/api/assets/{asset}/works',json=base).status_code==422
    entry=client.post(f'/api/assets/{asset}/works',json={**base,'seal_note':'Корпус не опечатан после ремонта'})
    assert entry.status_code==201,entry.text
    assert client.get(f'/api/assets/{asset}').json()['seal_state']=='unsealed_after_repair'
    assert client.post(f'/api/assets/{asset}/requests/{rid}/close',json={'resolution':'Работы проведены, корпус отмечен как не опечатанный'}).status_code==200
    assert client.get(f'/api/assets/{asset}/requests').json()[0]['status']=='closed'
    assert len(client.get(f'/api/assets/{asset}/works').json())==1
    assert client.post(f'/api/assets/{asset}/works',json={**base,'seal_note':'Повторная запись'}).status_code==409
    inspection={'inspector':'ИБ инспектор','checklist':{'unauthorized_content':'violation','seals':'violation'},
                'violation_categories':['unauthorized_files','physical_security'],
                'finding_summary':'Обнаружено нарушение политики и отсутствие пломбы',
                'corrective_action':'Зарегистрировать замечание и устранить нарушения','status':'violations'}
    test=client.post(f'/api/assets/{asset}/inspections',json=inspection)
    assert test.status_code==201,test.text
    assert client.post(f'/api/assets/{asset}/inspections',json={**inspection,'status':'passed'}).status_code==422
    assert client.get(f'/api/assets/{asset}/inspections').json()[0]['violation_categories']==inspection['violation_categories']
    status=client.get('/api/inspections/quarterly-status').json()
    assert len(status['results'])==1 and status['results'][0]['inspected']
    assert client.get('/api/audit?entity_type=asset&entity_id='+str(asset)).status_code==200


def test_reader_cannot_write_asset_log(client):
    from argon2 import PasswordHasher
    from app.db import SessionLocal
    from app.models import User
    from fastapi.testclient import TestClient
    from app.main import app
    oi,aid=create(client)
    with SessionLocal.begin() as db:
        db.add(User(username='viewer',role='viewer',password_hash=PasswordHasher().hash('view-password-123')))
    with TestClient(app) as reader:
        auth=reader.post('/api/auth/login',json={'username':'viewer','password':'view-password-123'}).json()
        reader.headers.update({'X-CSRF-Token':auth['csrf']})
        assert reader.get(f'/api/assets/{aid}/works').status_code==200
        assert reader.post(f'/api/assets/{aid}/components',json={'kind':'disk','serial_number':'ABC'}).status_code==403
        assert reader.post(f'/api/assets/{aid}/inspections',json={'inspector':'ИБ', 'finding_summary':'Тестовое описание', 'checklist':{'seals':'ok'}, 'status':'passed'}).status_code==403
