"""Configured recurring controls and evidence-backed completion (compatible with original 0001 create_all)."""
from alembic import op
import sqlalchemy as sa
from app.models import ControlRule

revision = "0006_control_rules"
down_revision = "0005_automation"
branch_labels = None
depends_on = None

NEW_COLUMNS = (
    sa.Column("rule_id", sa.Integer(), nullable=True),
    sa.Column("assignee", sa.String(180), nullable=False, server_default=""),
    sa.Column("evidence_document_id", sa.Integer(), nullable=True),
    sa.Column("completion_note", sa.Text(), nullable=False, server_default=""),
    sa.Column("completed_by", sa.Integer(), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("remote_status", sa.String(120), nullable=False, server_default=""),
    sa.Column("remote_checked_at", sa.DateTime(timezone=True), nullable=True),
)
FK = (
    ("fk_planned_rule", "rule_id", "control_rules"),
    ("fk_planned_evidence", "evidence_document_id", "documents"),
    ("fk_planned_completed_by", "completed_by", "users"),
)


def upgrade():
    bind = op.get_bind()
    ControlRule.__table__.create(bind, checkfirst=True)
    inspect = sa.inspect(bind)
    columns = {c['name'] for c in inspect.get_columns('planned_activities')}
    existing_fk_cols = {tuple(f['constrained_columns']) for f in inspect.get_foreign_keys('planned_activities')}
    indexes = {i['name'] for i in inspect.get_indexes('planned_activities')}
    missing_cols = [c for c in NEW_COLUMNS if c.name not in columns]
    missing_fk = [(name, col, table) for name, col, table in FK if (col,) not in existing_fk_cols]
    missing_index = 'ix_planned_rule_deadline' not in indexes
    if missing_cols or missing_fk or missing_index:
        with op.batch_alter_table('planned_activities') as batch:
            for col in missing_cols:
                batch.add_column(col)
            for name, col, table in missing_fk:
                batch.create_foreign_key(name, table, [col], ['id'])
            if missing_index:
                batch.create_index('ix_planned_rule_deadline', ['rule_id', 'deadline'])


def downgrade():
    # A downgrade is destructive for all v0.5 rule links/completion evidence.
    bind = op.get_bind()
    inspect = sa.inspect(bind)
    cols = {c['name'] for c in inspect.get_columns('planned_activities')}
    indexes = {i['name'] for i in inspect.get_indexes('planned_activities')}
    existing_fk_cols = {tuple(f['constrained_columns']):f['name'] for f in inspect.get_foreign_keys('planned_activities')}
    with op.batch_alter_table('planned_activities') as batch:
        if 'ix_planned_rule_deadline' in indexes:
            batch.drop_index('ix_planned_rule_deadline')
        for _, col, _ in FK:
            if (col,) in existing_fk_cols:
                batch.drop_constraint(existing_fk_cols[(col,)], type_='foreignkey')
        for col in reversed(NEW_COLUMNS):
            if col.name in cols:
                batch.drop_column(col.name)
    ControlRule.__table__.drop(bind, checkfirst=True)
