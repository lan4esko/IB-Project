"""v0.5 tests on disposable SQLite; never contact OpenProject."""
from datetime import date
from fastapi.testclient import TestClient
from app.db import SessionLocal
from app.main import app
from app.models import ControlRule, PlannedActivity
from app.automation import plan, month_due
from test_end_to_end import client
from test_governance import auth_as


def test_calendar_anchor_and_global_asset_rules(client):
    assert month_due(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert month_due(date(2026, 1, 31), 2) == date(2026, 3, 31)
    oi1 = client.post('/api/objects', json={'code': 'OI-1', 'name': 'ОИ 1'}).json()
    oi2 = client.post('/api/objects', json={'code': 'OI-2', 'name': 'ОИ 2'}).json()
    client.post('/api/assets', json={'code': 'SVT-1', 'oi_id': oi1['id']})
    client.post('/api/assets', json={'code': 'SVT-2', 'oi_id': oi1['id']})
    client.post('/api/assets', json={'code': 'SVT-3', 'oi_id': oi2['id'], 'status': 'retired'})
    created = client.post('/api/automation/rules', json={'title': 'Проверка ПО',
        'scope': 'asset', 'first_due': '2026-10-31', 'interval_months': 1,
        'assignee': 'Специалист ИБ'})
    assert created.status_code == 201, created.text
    with SessionLocal() as db:
        preview = plan(db, date(2026, 10, 15), write=False, horizon_days=50)
        custom = [x for x in preview['preview'] if x['event_type'] == 'custom_control']
        assert len(custom) == 4, custom  # two active assets, Oct + Nov
        first = plan(db, date(2026, 10, 15), write=True, horizon_days=50)
        again = plan(db, date(2026, 10, 15), write=True, horizon_days=50)
        assert first['new_count'] >= 4
        assert again['new_count'] == 0
        assert db.query(PlannedActivity).filter_by(event_type='custom_control').count() == 4
        assert all(x.assignee == 'Специалист ИБ' for x in db.query(PlannedActivity).filter_by(event_type='custom_control'))


def test_evidence_required_and_rule_disable(client):
    obj = client.post('/api/objects', json={'code': 'OI-R', 'name': 'Регламентный ОИ'}).json()
    rule = client.post('/api/automation/rules', json={'title': 'Контроль учётных записей', 'scope': 'oi',
        'oi_id': obj['id'], 'first_due': '2026-10-20', 'interval_months': 3}).json()
    with SessionLocal() as db:
        plan(db, date(2026, 10, 18), write=True)
    item = next(x for x in client.get('/api/automation/activities').json() if x['rule_id'] == rule['id'])
    assert client.post(f"/api/automation/activities/{item['id']}/complete", json={
        'evidence_document_id': 9999, 'note': 'Документ не зарегистрирован'}).status_code == 404
    doc = client.post('/api/documents?title=Акт', files={
        'file': ('act.txt', b'proof for test control')}).json()
    ok = client.post(f"/api/automation/activities/{item['id']}/complete", json={
        'evidence_document_id': doc['id'], 'note': 'Контроль выполнен, акт зарегистрирован'})
    assert ok.status_code == 200, ok.text
    assert ok.json()['status'] == 'completed'
    assert ok.json()['completed_by'] == 1
    assert client.post(f"/api/automation/activities/{item['id']}/complete", json={
        'evidence_document_id': doc['id'], 'note': 'Повторное подтверждение контроля'}).status_code == 409
    with SessionLocal() as db:
        plan(db, date(2026, 10, 18), write=True)
        assert db.get(PlannedActivity, item['id']).status == 'completed'
    stop = client.post(f"/api/automation/rules/{rule['id']}/disable")
    assert stop.status_code == 200
    assert stop.json()['active'] is False
    assert client.post(f"/api/automation/rules/{rule['id']}/disable").status_code == 409
    assert client.post(f"/api/automation/rules/{rule['id']}/enable").status_code == 200


def test_summary_and_authz(client):
    oi = client.post('/api/objects', json={'code': 'OI-A', 'name': 'Управляемый ОИ'}).json()
    assert client.post('/api/automation/rules', json={'title': 'Ежегодная аттестация',
        'scope': 'oi', 'oi_id': 9999, 'first_due': '2026-10-20', 'interval_months': 12}).status_code == 404
    assert client.post('/api/automation/rules', json={'title': 'Регламент',
        'scope': 'bad', 'first_due': '2026-10-20', 'interval_months': 2}).status_code == 422
    created = client.post('/api/automation/rules', json={'title': 'Контроль настроек доступа',
        'scope': 'oi', 'oi_id': oi['id'], 'first_due': '2026-10-20', 'interval_months': 12})
    assert created.status_code == 201
    with SessionLocal() as db:
        plan(db, date(2026, 10, 18), write=True)
    assert client.get('/api/automation/summary').status_code == 200
    assert any(x['oi_id'] == oi['id'] for x in client.get('/api/automation/summary').json()['by_oi'])
    unauthed = TestClient(app)
    assert unauthed.get('/api/automation/rules').status_code == 401
    assert unauthed.get('/api/automation/summary').status_code == 401
    editor = client.post('/api/users', json={'username': 'editor05', 'display_name': 'ИБ',
        'role': 'editor', 'initial_password': 'editor-password-123'})
    assert editor.status_code == 201
    with auth_as('editor05', 'editor-password-123')[0] as cli:
        cli.post('/api/auth/password', json={'old_password': 'editor-password-123',
            'new_password': 'editor-new-password-789'})
        assert cli.get('/api/automation/rules').status_code == 200
        assert cli.post('/api/automation/rules', json={'title': 'Запрет оператору',
            'scope': 'oi', 'first_due': '2026-10-20', 'interval_months': 1}).status_code == 403
        assert cli.post(f"/api/automation/rules/{created.json()['id']}/disable").status_code == 403


def test_remote_status_is_read_only_and_audited(client, monkeypatch):
    from app import main as m
    obj = client.post('/api/objects', json={'code': 'OI-OP', 'name': 'Тест OP',
        'attestation_valid_until': '2026-01-01', 'openproject_project_id': 17}).json()
    client.post('/api/automation/plan')
    item = next(x for x in client.get('/api/automation/activities').json() if x['event_type'] == 'attestation')
    assert client.post(f"/api/automation/activities/{item['id']}/reconcile").status_code == 409
    with SessionLocal.begin() as db:
        row = db.get(PlannedActivity, item['id'])
        row.sync_status = 'published'
        row.openproject_work_package_id = 123
    received = []
    def fake_fetch(work_id):
        received.append(work_id)
        return {'id': work_id, 'status': 'Closed', 'subject': 'Тест OP', 'due_date': None, 'assignee': ''}
    monkeypatch.setattr(m, 'op_fetch_work_package', fake_fetch)
    data = client.post(f"/api/automation/activities/{item['id']}/reconcile")
    assert data.status_code == 200, data.text
    assert received == [123]
    assert data.json()['activity']['remote_status'] == 'Closed'
    assert data.json()['activity']['status'] == 'open'  # remote closure alone is not local evidence
    assert data.json()['activity']['remote_checked_at']
    monkeypatch.setattr(m, 'op_fetch_work_package', lambda _: (_ for _ in ()).throw(RuntimeError('SECRET-DO-NOT-EXPOSE')))
    failed = client.post(f"/api/automation/activities/{item['id']}/reconcile")
    assert failed.status_code == 502 and 'SECRET-DO-NOT-EXPOSE' not in failed.text
