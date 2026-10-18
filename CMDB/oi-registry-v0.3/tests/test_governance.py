"""Identity, submissions, attestation alert, MFP metadata, report on disposable DB."""
import datetime as dt
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import AuditEvent, User
from test_end_to_end import client


def auth_as(name, password):
    c=TestClient(app)
    r=c.post('/api/auth/login', json={'username':name,'password':password})
    assert r.status_code==200,r.text
    c.headers.update({'X-CSRF-Token':r.json()['csrf']})
    return c, r.json()


def test_roles_proposals_weekly_and_audit(client):
    ed=client.post('/api/users',json={'username':'editor01','display_name':'Инженер БД','role':'editor','initial_password':'editor-password-123'})
    req=client.post('/api/users',json={'username':'requester01','display_name':'Ответственный за ОИ','role':'requester','initial_password':'requester-password-123'})
    assert ed.status_code==201,ed.text
    assert req.status_code==201,req.text
    with auth_as('requester01','requester-password-123')[0] as requester:
        assert requester.get('/api/objects').status_code==403
        assert requester.post('/api/proposals',json={'code':'OI-01','name':'Новый учебный объект'}).status_code==403
        password=requester.post('/api/auth/password',json={'old_password':'requester-password-123','new_password':'requester-private-456'})
        assert password.status_code==200,password.text
        prop=requester.post('/api/proposals',json={'code':'OI-01','name':'Новый учебный объект','location':'Каб 2'})
        assert prop.status_code==201,prop.text
        prop_id=prop.json()['id']
        attachment=requester.post(f'/api/proposals/{prop_id}/attachment',files={'file':('form.txt',b'Form for OI-01')})
        assert attachment.status_code==201,attachment.text
        assert requester.get(f'/api/proposals/{prop_id}/attachment/file').status_code==200
        assert requester.get('/api/documents').status_code==403
        assert requester.post('/api/objects',json={'code':'HI','name':'Не должно работать'}).status_code==403
        assert requester.post(f'/api/proposals/{prop_id}/review',json={'decision':'approved','review_note':'Проверено согласно заявке'}).status_code==403
        assert len(requester.get('/api/proposals').json())==1
    with auth_as('editor01','editor-password-123')[0] as editor:
        editor.post('/api/auth/password',json={'old_password':'editor-password-123','new_password':'editor-private-456'})
        assert editor.get('/api/users').status_code==403
        assert editor.post('/api/fields',json={'entity_type':'oi','name':'Test','field_type':'text'}).status_code==403
        approved=editor.post(f'/api/proposals/{prop_id}/review',json={'decision':'approved','review_note':'Подтверждён состав документов и намерение создания объекта'})
        assert approved.status_code==200,approved.text
        oi_id=approved.json()['created_oi_id']
        asset=editor.post('/api/assets',json={'code':'SVT-01','oi_id':oi_id})
        assert asset.status_code==201,asset.text
        work=editor.post(f'/api/assets/{asset.json()["id"]}/works',json={
            'performer':'Инженер БД','work_type':'diagnostics',
            'actions':'Проверка аппаратных компонентов', 'result':'Неисправность не обнаружена',
            'seal_state_after':'sealed'})
        assert work.status_code==201,work.text
        report=editor.get('/api/reports/weekly').json()
        assert len(report['work_entries'])==1
        assert report['user']['username']=='editor01'
        assert any(x['action']=='work_recorded' for x in report['activity'])
        assert editor.get('/api/reports/weekly?user_id=1').status_code==403
        assert editor.get('/api/reports/weekly?format=csv').status_code==200
        assert editor.get('/api/audit').status_code==403
    admin_report=client.get('/api/reports/weekly?user_id='+str(ed.json()['id']))
    assert admin_report.status_code==200
    events=client.get('/api/audit').json()
    assert any(x['action']=='proposal_reviewed' and x['request_id'] for x in events)
    assert client.post(f'/api/proposals/{prop_id}/review',json={'decision':'rejected','review_note':'Неверные сведения'}) .status_code==409
    assert client.patch('/api/users/1',json={'role':'requester'}).status_code==409
    assert client.patch('/api/users/'+str(ed.json()['id']),json={'active':False}).status_code==200
    with TestClient(app) as blocked:
        assert blocked.post('/api/auth/login',json={'username':'editor01','password':'editor-private-456'}).status_code==401


def test_expiration_and_mfp_driver_location(client):
    from datetime import datetime, timedelta
    tomorrow=(datetime.now(dt.timezone.utc).date()+timedelta(days=3)).isoformat()
    oi=client.post('/api/objects',json={'code':'OI-01','name':'ГИС','attestation_valid_until':tomorrow,'attestation_notice_days':30})
    assert oi.status_code==201,oi.text
    oid=oi.json()['id']
    due=client.get('/api/attestations/due').json()
    assert due['count']==1 and due['items'][0]['status']=='due_soon'
    asset=client.post('/api/assets',json={'code':'SVT-01','oi_id':oid}).json()['id']
    bad=client.post(f'/api/objects/{oid}/peripherals',json={'name':'МФУ'},)
    assert bad.status_code==422
    good=client.post(f'/api/objects/{oid}/peripherals',json={
        'name':'МФУ кабинет','serial_number':'MFP-43567','manufacturer':'МФУ-Производитель',
        'model':'Модель-42','inventory_number':'INV-42','media_present':True,
        'media_kind':'SSD','media_serial_number':'SSD-001', 'media_inventory_number':'STOR-001'})
    assert good.status_code==201,good.text
    mfp=good.json()
    assert mfp['media_present'] is True
    assert mfp['media_serial_number']=='SSD-001'
    changed=client.patch(f'/api/objects/{oid}/peripherals/{mfp["id"]}',json={'media_serial_number':'SSD-002'})
    assert changed.status_code==200,changed.text
    assert changed.json()['media_serial_number']=='SSD-002'
    assert any(e['action']=='peripheral_updated' for e in client.get('/api/audit').json())
    badlink=client.post(f'/api/assets/{asset}/peripherals',json={
        'peripheral_id':mfp['id'],'reason':'Допущено в составе ОИ','driver_smb_path':'smb://user:password@host/driver.pkg'})
    assert badlink.status_code==422
    link=client.post(f'/api/assets/{asset}/peripherals',json={
        'peripheral_id':mfp['id'],'reason':'Допущено в составе ОИ','connection_type':'lan',
        'driver_name':'CUPS','driver_version':'3.1',
        'driver_smb_path':'smb://srv.local/drivers/mfp.deb', 'driver_sha256':'a'*64})
    assert link.status_code==201,link.text
    assert client.get(f'/api/assets/{asset}/peripherals').json()[0]['driver_smb_path'].startswith('smb://')
    b=client.post(f'/api/objects/{oid}/baselines',json={'version':'1.0','notes':'Опись комплекта'})
    assert b.status_code==201,b.text
    patch=client.patch(f'/api/objects/{oid}',json={'attestation_notice_days':45})
    assert patch.status_code==200,patch.text
    assert client.get(f'/api/objects/{oid}').json()['attestation_notice_days']==45


def test_requested_week_requires_monday(client):
    assert client.get('/api/reports/weekly?week_start=2026-10-13').status_code==422
