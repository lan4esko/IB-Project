"""Control planning without OpenProject side-effects (disposable SQLite)."""
from datetime import date, datetime, timezone
from fastapi.testclient import TestClient
from app.db import SessionLocal
from app.models import InformationObject, Asset, AssetInspection, PlannedActivity
from app.automation import plan, quarter_bounds
from app.main import app
from test_end_to_end import client
from test_governance import auth_as


def test_attestation_deadline_and_quarter_events_idempotent(client):
    obj=client.post('/api/objects',json={'code':'OI-A','name':'Тестовый объект',
        'attestation_valid_until':'2026-12-10','attestation_notice_days':90,'openproject_project_id':27}).json()
    asset=client.post('/api/assets',json={'code':'SVT-A','oi_id':obj['id']}).json()
    with SessionLocal() as session:
        preview=plan(session,date(2026,10,18),write=False)
        assert preview['new_count']==2,preview
        assert preview['written'] is False
        assert session.query(PlannedActivity).count()==0
        first=plan(session,date(2026,10,18),write=True)
        assert first['new_count']==2
        assert {i['event_type'] for i in first['preview']}=={'attestation','quarterly_inspection'}
        second=plan(session,date(2026,10,18),write=True)
        assert second['new_count']==0
        assert session.query(PlannedActivity).count()==2
        att=session.query(PlannedActivity).filter_by(event_type='attestation').one()
        assert att.openproject_project_id==27
        assert att.deadline==date(2026,12,10)
        item=session.query(PlannedActivity).filter_by(event_type='quarterly_inspection').one()
        assert item.deadline==date(2026,12,31)
        session.add(AssetInspection(asset_id=asset['id'],
            inspected_at=datetime(2026,11,14,tzinfo=timezone.utc),
            inspector='ИБ',checklist={'software':'ok'},violation_categories=[],
            finding_summary='Проверено',status='passed',created_by=1))
        session.commit()
        after=plan(session,date(2026,11,15),write=True)
        assert after['new_count']==0
        assert session.get(PlannedActivity,item.id).status=='satisfied'


def test_attestation_change_generates_new_period_not_delete_history(client):
    obj=client.post('/api/objects',json={'code':'OI-A','name':'ОИ',
       'attestation_valid_until':'2026-10-01'}).json()
    with SessionLocal() as session:
        assert plan(session,date(2026,10,18),write=True)['new_count']==1
    client.patch(f'/api/objects/{obj["id"]}',json={'attestation_valid_until':'2027-03-01'})
    with SessionLocal() as session:
        assert plan(session,date(2026,10,18),write=True)['new_count']==0 # outside 90 days
        assert session.query(PlannedActivity).one().status=='superseded'
        assert plan(session,date(2027,2,10),write=True)['new_count']==1
        assert session.query(PlannedActivity).count()==2


def test_access_preview_plan_and_disabled_external_publish(client,monkeypatch):
    obj=client.post('/api/objects',json={'code':'OI-A','name':'ОИ',
       'attestation_valid_until':'2026-01-01','openproject_project_id':21}).json()
    item=client.post('/api/automation/plan')
    assert item.status_code==200,item.text
    items=client.get('/api/automation/activities').json()
    assert any(x['event_type']=='attestation' for x in items)
    ident=next(x['id'] for x in items if x['event_type']=='attestation')
    assert client.get('/api/automation/integration').json()['enabled'] is False
    assert client.post(f'/api/automation/activities/{ident}/publish').status_code==409
    bad=client.post(f'/api/automation/activities/{ident}/acknowledge',json={'note':'too short'})
    assert bad.status_code==422
    good=client.post(f'/api/automation/activities/{ident}/acknowledge',json={'note':'Данные проверены ответственным'} )
    assert good.status_code==200,good.text
    assert client.post(f'/api/automation/activities/{ident}/acknowledge',json={'note':'Повторно согласовано'}).status_code==409
    assert client.post('/api/automation/plan').json()['new_count']==0
    noauth=TestClient(app)
    assert noauth.get('/api/automation/activities').status_code==401


def test_editor_cannot_publish_and_requester_restricted(client):
    created=client.post('/api/users',json={'username':'op04','display_name':'Оператор',
        'role':'editor','initial_password':'op04-password-123'})
    assert created.status_code==201
    with auth_as('op04','op04-password-123')[0] as editor:
        editor.post('/api/auth/password',json={'old_password':'op04-password-123','new_password':'another-password-456'})
        assert editor.get('/api/automation/activities').status_code==200
        assert editor.get('/api/automation/preview').status_code==200
        assert editor.post('/api/automation/plan').status_code==200
        assert editor.get('/api/automation/integration').status_code==403


def test_quarter_boundaries():
    assert quarter_bounds(date(2026,10,18))==(date(2026,10,1),date(2026,12,31),'2026Q4')
    assert quarter_bounds(date(2027,1,1))==(date(2027,1,1),date(2027,3,31),'2027Q1')


def test_manual_publish_mocked_only_after_explicit_opt_in(client,monkeypatch):
    from app import main as m
    oi=client.post('/api/objects',json={'code':'OI-OP','name':'Тест OpenProject',
        'attestation_valid_until':'2025-01-01','openproject_project_id':7}).json()
    planned=client.post('/api/automation/plan').json()
    activity=next(x for x in client.get('/api/automation/activities').json() if x['event_type']=='attestation')
    # Application does not create remote tasks on local planning; publishing is a separate POST.
    monkeypatch.setenv('OI_OP_SYNC_ENABLED','true')
    monkeypatch.setenv('OI_OP_BASE_URL','https://openproject.example.test')
    monkeypatch.setenv('OI_OP_API_KEY','test-only-secret-do-not-use')
    monkeypatch.setenv('OI_OP_TYPE_ID','1')
    calls=[]
    def fake_publish(record):
        calls.append(record.event_key)
        return 405
    monkeypatch.setattr(m,'op_publish',fake_publish)
    r=client.post(f'/api/automation/activities/{activity["id"]}/publish')
    assert r.status_code==200,r.text
    assert r.json()['sync_status']=='published'
    assert r.json()['openproject_work_package_id']==405
    assert len(calls)==1
    assert client.post(f'/api/automation/activities/{activity["id"]}/publish').status_code==409


def test_uncertain_publish_requires_review(client,monkeypatch):
    from app import main as m
    oi=client.post('/api/objects',json={'code':'OI-OP','name':'Тест OpenProject',
        'attestation_valid_until':'2025-01-01','openproject_project_id':7}).json()
    client.post('/api/automation/plan')
    activity=next(x for x in client.get('/api/automation/activities').json() if x['event_type']=='attestation')
    monkeypatch.setenv('OI_OP_SYNC_ENABLED','true')
    monkeypatch.setenv('OI_OP_BASE_URL','https://openproject.example.test')
    monkeypatch.setenv('OI_OP_API_KEY','test-only-secret')
    monkeypatch.setenv('OI_OP_TYPE_ID','1')
    def fail(_):raise TimeoutError('test timeout')
    monkeypatch.setattr(m,'op_publish',fail)
    result=client.post(f'/api/automation/activities/{activity["id"]}/publish')
    assert result.status_code==502
    item=next(x for x in client.get('/api/automation/activities').json() if x['event_type']=='attestation')
    assert item['sync_status']=='needs_review'
    assert client.post(f'/api/automation/activities/{activity["id"]}/publish').status_code==409
