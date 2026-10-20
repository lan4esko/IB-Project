"""v0.7.0-rc1 regression: assets and media, OI reviews, configurable fields, safe queries."""
from test_end_to_end import client
from app.db import SessionLocal
from app.models import User
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from app.main import app


def test_asset_media_and_reissue_history(client):
    asset=client.post('/api/assets',json={'code':'SVT1','savz_name':'AV','savz_version':'1.0',
        'szi_nsd_name':'Guard','szi_nsd_version':'2.0'}).json()
    aid=asset['id']
    assert asset['savz_name']=='AV' and asset['szi_nsd_version']=='2.0'
    d1=client.post(f'/api/assets/{aid}/mni',json={'serial_number':'D1','accounting_number':'M-1','media_type':'SSD'})
    assert d1.status_code==201,d1.text
    assert client.post(f'/api/assets/{aid}/mni',json={'serial_number':'D2','accounting_number':'M-2','media_type':'HDD'}).status_code==201
    assert len(client.get(f'/api/assets/{aid}/mni').json())==2
    assert client.post(f'/api/assets/{aid}/mni',json={'serial_number':'D1','accounting_number':'OTHER'}).status_code==409
    z=client.post(f'/api/assets/{aid}/zmni',json={'serial_number':'USB-1','accounting_number':'Z-1',
        'container_filename':'old.enc','container_issued_on':'2023-10-20'})
    assert z.status_code==201,z.text
    zid=z.json()['id']
    renewed=client.post(f'/api/assets/{aid}/zmni/{zid}/container',json={
        'container_filename':'new.enc','container_issued_on':'2026-10-20'})
    assert renewed.status_code==200,renewed.text
    assert renewed.json()['container_filename']=='new.enc'
    history=client.get(f'/api/assets/{aid}/zmni/{zid}/history').json()
    assert [x['container_filename'] for x in history]==['old.enc','new.enc']
    assert client.post(f'/api/assets/{aid}/zmni/{zid}/container',json={
        'container_filename':'old.again','container_issued_on':'2020-01-01'}).status_code==422
    asset2=client.post('/api/assets',json={'code':'SVT2'}).json()
    assert client.get(f'/api/assets/{asset2["id"]}/zmni/{zid}/history').status_code==404


def test_oi_reviews_with_independent_remediation(client):
    oi=client.post('/api/objects',json={'code':'OI1','name':'Registry'}).json()
    oid=oi['id']
    rev=client.post(f'/api/objects/{oid}/reviews',json={'reviewed_on':'2026-10-20',
        'reviewer':'Auditor','report_smb_path':r'\\server\reports\act.pdf'})
    assert rev.status_code==201,rev.text
    rid=rev.json()['id']
    ids=[]
    for category in ('deficiency','violation'):
        f=client.post(f'/api/objects/{oid}/reviews/{rid}/findings',json={'category':category,'description':'Found '+category})
        assert f.status_code==201,f.text
        ids.append(f.json()['id'])
    result=client.patch(f'/api/objects/{oid}/reviews/{rid}/findings/{ids[0]}',json={
        'resolved':True,'corrective_action':'Fixed'})
    assert result.status_code==200,result.text
    reviews=client.get(f'/api/objects/{oid}/reviews').json()
    assert len(reviews)==1 and reviews[0]['open_count']==1
    assert len(reviews[0]['findings'])==2
    assert reviews[0]['findings'][0]['resolved'] and not reviews[0]['findings'][1]['resolved']


def test_custom_fields_in_creation_and_requests(client):
    reqf=client.post('/api/fields',json={'entity_type':'request','name':'Ответственный','required':True})
    assetf=client.post('/api/fields',json={'entity_type':'asset','name':'Группа','required':True})
    assert reqf.status_code==201 and assetf.status_code==201
    rf=str(reqf.json()['id']);af=str(assetf.json()['id'])
    assert client.post('/api/assets',json={'code':'SVT-NO-FIELD'}).status_code==422
    assert client.post('/api/assets',json={'code':'SVT1','custom_fields':{af:'X'}}).status_code==201
    assert client.post('/api/registry-requests',json={'full_name':'Иванов'}).status_code==422
    ok=client.post('/api/registry-requests',json={'full_name':'Иванов','custom_fields':{rf:'Руководитель'}})
    assert ok.status_code==201,ok.text
    listed=client.get('/api/registry-requests').json()[0]
    assert listed['custom_fields'][rf]=='Руководитель'
    bad=client.post('/api/registry-requests',json={'full_name':'Петров','custom_fields':{'9999':'x'}})
    assert bad.status_code==422


def test_safe_query_selected_custom_fields_and_export(client):
    field=client.post('/api/fields',json={'entity_type':'asset','name':'Отдел'}).json()
    fid=str(field['id'])
    client.post('/api/assets',json={'code':'A01','network_segment':'SEG',
        'savz_name':'Antivirus','custom_fields':{fid:'ИТ'}})
    client.post('/api/assets',json={'code':'A02','network_segment':'OTHER'})
    params={'columns':['code','network_segment','savz_name',f'custom:{fid}'],
        'filters':[{'field':'network_segment','op':'eq','value':'SEG'},
                   {'field':f'custom:{fid}','op':'contains','value':'ИТ'}]}
    resp=client.post('/api/assets/query/preview',json=params)
    assert resp.status_code==200,resp.text
    assert resp.json()['rows']==[{'code':'A01','network_segment':'SEG','savz_name':'Antivirus',f'custom:{fid}':'ИТ'}]
    csv=client.post('/api/assets/query/export.csv',json=params)
    assert csv.status_code==200,csv.text
    assert 'Antivirus' in csv.text and 'Отдел' in csv.text
    assert client.post('/api/assets/query/preview',json={'columns':['__class__'],'filters':[]}).status_code==422
    assert client.post('/api/assets/query/preview',json={'columns':['code'],
        'filters':[{'field':'code','op':'drop table','value':'A01'}]}).status_code==422
    # spreadsheet formula injection is neutralized
    client.post('/api/assets',json={'code':'B01','serial_number':'=HYPERLINK("http://example")'})
    out=client.post('/api/assets/query/export.csv',json={'columns':['serial_number'],'filters':[]})
    assert out.status_code==200 and "'=HYPERLINK" in out.text


def test_admin_only_fields_and_csv_preview(client):
    with SessionLocal.begin() as db:
        db.add(User(username='editor',role='editor',password_hash=PasswordHasher().hash('sample-password-123')))
    with TestClient(app) as editor:
        login=editor.post('/api/auth/login',json={'username':'editor','password':'sample-password-123'})
        editor.headers.update({'X-CSRF-Token':login.json()['csrf']})
        assert editor.post('/api/fields',json={'entity_type':'asset','name':'Denied'}).status_code==403
        assert editor.post('/api/assets/import/preview',data={'mode':'merge'},
            files={'file':('test.csv',b'code;oi_code\r\nA01;\r\n')}).status_code==403
        assert editor.post('/api/assets/query/preview',json={'columns':['code']}).status_code==200
