"""New registration: standalone assets, SMB refs, reusable system types, guarded CSV import."""
from test_end_to_end import client
from app.db import SessionLocal
from app.models import Asset, RegistryRequest


def create_asset(client, code='SVT-NEW', oi_id=None):
    data = {'code': code, 'model': 'PC'}
    if oi_id is not None:
        data['oi_id'] = oi_id
    response = client.post('/api/assets', json=data)
    assert response.status_code == 201, response.text
    return response.json()


def preview(client, csv_bytes, mode):
    return client.post('/api/assets/import/preview', data={'mode': mode},
                       files={'file': ('assets.csv', csv_bytes, 'text/csv')})


def confirm(client, csv_bytes, plan, mode, phrase=None):
    return client.post('/api/assets/import/commit', data={
        'mode': mode, 'plan_id': plan['plan_id'],
        'confirmation_phrase': phrase if phrase is not None else plan['confirmation_phrase']},
        files={'file': ('assets.csv', csv_bytes, 'text/csv')})


def test_smb_attestation_and_standalone_asset(client):
    data = client.post('/api/objects', json={'code': 'OI1', 'name': 'Test',
        'attestation_smb_path': r'\\server\docs\attestation.pdf'})
    assert data.status_code == 201, data.text
    assert data.json()['attestation_smb_path'].startswith('\\\\server')
    a = create_asset(client)
    assert a['oi_id'] is None
    all_assets = client.get('/api/assets').json()
    assert all_assets['total'] == 1 and all_assets['items'][0]['oi_code'] is None
    assert client.get('/api/assets?q=SVT-NEW').json()['total'] == 1
    updated = client.patch('/api/assets/'+str(a['id']), json={'oi_id': data.json()['id']})
    assert updated.status_code == 200
    unassign = client.patch('/api/assets/'+str(a['id']), json={'oi_id': None})
    assert unassign.status_code == 200 and unassign.json()['oi_id'] is None


def test_registry_requests_without_system_type(client):
    a = create_asset(client)
    for i in range(2):
        res = client.post('/api/registry-requests', json={
            'segment': 'SEG01', 'full_name': f'Сотрудник {i}',
            'ip_address':'192.0.2.8', 'scan_smb_path':r'\\srv\applications\file.pdf',
            'asset_id':a['id']})
        assert res.status_code == 201, res.text
        assert res.json()['system_type_id'] is None
    values = client.get('/api/registry-requests').json()
    assert len(values)==2
    assert values[0]['asset_code']==a['code']
    assert 'system_type_name' not in values[0]
    bad = client.post('/api/registry-requests',json={'segment':'X','full_name':'Test User',
        'ip_address':'999.1.1.1', 'scan_smb_path':'file:///tmp/scan'})
    assert bad.status_code==422
    update=client.patch('/api/registry-requests/'+str(values[0]['id']),json={
        'segment':'SEG02','full_name':'Сотрудник И.', 'ip_address':'192.0.2.9',
        'scan_smb_path':r'\\srv\applications\updated.pdf', 'asset_id':None})
    assert update.status_code==200, update.text
    assert update.json()['system_type_id'] is None


def test_legacy_system_type_reference_preserved(client):
    # Old rows stay linked to the legacy dictionary when edited without the field.
    from app.models import RegistryRequest, SystemType
    with SessionLocal.begin() as db:
        st=SystemType(name='Устаревший тип')
        db.add(st);db.flush()
        req=RegistryRequest(segment='old',full_name='Исторический сотрудник',
            system_type_id=st.id,created_by=1)
        db.add(req);db.flush();request_id=req.id;legacy_id=st.id
    response=client.patch(f'/api/registry-requests/{request_id}',json={
        'segment':'new','full_name':'Исторический сотрудник', 'ip_address':'',
        'scan_smb_path':'', 'asset_id':None})
    assert response.status_code==200,response.text
    with SessionLocal() as db:
        assert db.get(RegistryRequest,request_id).system_type_id==legacy_id


def test_csv_three_modes_preview_and_confirmation(client):
    a = create_asset(client)
    content = client.get('/api/assets/export.csv').content
    missing = client.post('/api/assets/import/preview', files={'file':('a.csv',content)})
    assert missing.status_code == 422
    p = preview(client, content, 'merge')
    assert p.status_code == 200, p.text
    plan = p.json()
    assert set(plan['comparisons']) == {'merge','copy','replace'}
    assert confirm(client, content, plan, 'merge', 'wrong').status_code == 403
    assert confirm(client, content, plan, 'replace').status_code == 409
    assert confirm(client, content, plan, 'merge').status_code == 200
    assert confirm(client, content, plan, 'merge').status_code == 409
    p = preview(client, content, 'copy').json()
    assert confirm(client, content, p, 'copy').status_code == 200
    assert client.get('/api/assets').json()['total'] == 2
    csv_changed=content.replace(b';PC;',b';NewPC;')
    p = preview(client, csv_changed, 'replace').json()
    assert p['selected']['update'] == 1
    assert confirm(client,csv_changed,p,'replace').status_code == 200
    assert client.get('/api/assets/'+str(a['id'])).json()['model']=='NewPC'
    p = preview(client, content, 'replace').json()
    client.patch('/api/assets/'+str(a['id']), json={'model':'Changed concurrently'})
    assert confirm(client,content,p,'replace').status_code == 409


def test_csv_rejects_malformed(client):
    assert preview(client,b'not;csv\n1;2', 'copy').status_code == 422


def test_repair_journal_is_available_for_unassigned_asset(client):
    a = create_asset(client, 'SVT-REPAIR')
    response = client.post('/api/assets/'+str(a['id'])+'/works', json={
        'performer':'Техник А', 'work_type':'repair', 'actions':'Заменён блок питания',
        'result':'Проверен запуск станции', 'seal_state_after':'sealed'})
    assert response.status_code == 201, response.text
    data = client.get('/api/assets/'+str(a['id'])+'/works').json()
    assert len(data) == 1 and data[0]['work_type'] == 'repair'
