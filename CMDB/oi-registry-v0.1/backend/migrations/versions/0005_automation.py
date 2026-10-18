"""Scheduled control activities and safe OpenProject outbox."""
from alembic import op
from app.models import PlannedActivity
revision = "0005_automation"
down_revision = "0004_governance"
branch_labels = None
depends_on = None

def upgrade():
    PlannedActivity.__table__.create(op.get_bind(),checkfirst=True)

def downgrade():
    PlannedActivity.__table__.drop(op.get_bind(),checkfirst=True)
