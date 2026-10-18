#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose config -q
REV="$(docker compose exec -T oi-api alembic current)"
echo "$REV"
[[ "$REV" == *"0006_control_rules"* ]] || { echo 'ERROR: expected migration 0006_control_rules' >&2; exit 1; }
docker compose exec -T oi-api python - <<'PYCODE'
from sqlalchemy import inspect, text
from app.db import engine
from app.models import ControlRule, PlannedActivity
with engine.connect() as db:
    assert 'control_rules' in inspect(db).get_table_names()
    names={c['name'] for c in inspect(db).get_columns('planned_activities')}
    assert {'rule_id','assignee','evidence_document_id','completed_by','completed_at','remote_status'} <= names
    rules=db.execute(text('select count(*) from control_rules')).scalar_one()
    events=db.execute(text('select count(*) from planned_activities')).scalar_one()
    print('OK migration 0006; rules:',rules,'activities:',events)
PYCODE
printf 'OI Registry v0.5 migration smoke OK\n'
