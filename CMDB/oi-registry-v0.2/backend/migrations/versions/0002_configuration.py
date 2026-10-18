"""OI snapshots and configuration change requests; existing tables untouched."""
from alembic import op
from app.models import ConfigurationBaseline, ConfigurationChange

revision = "0002_configuration"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    ConfigurationBaseline.__table__.create(bind=bind, checkfirst=True)
    ConfigurationChange.__table__.create(bind=bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    ConfigurationChange.__table__.drop(bind=bind, checkfirst=True)
    ConfigurationBaseline.__table__.drop(bind=bind, checkfirst=True)
