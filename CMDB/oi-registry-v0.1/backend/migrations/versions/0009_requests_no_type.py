"""Remove mandatory system-type assignment for administrative requests, preserve history."""
from alembic import op
import sqlalchemy as sa

revision = '0009_requests_no_type'
down_revision = '0008_registry_v061'
branch_labels = None
depends_on = None


def upgrade():
    # Do not drop the old column/table: historical values remain available.
    with op.batch_alter_table('registry_requests') as batch:
        batch.alter_column('system_type_id', existing_type=sa.Integer(), nullable=True)


def downgrade():
    bind = op.get_bind()
    missing = bind.execute(sa.text('SELECT count(*) FROM registry_requests WHERE system_type_id IS NULL')).scalar_one()
    if missing:
        raise RuntimeError('Cannot downgrade: new requests without system type exist')
    with op.batch_alter_table('registry_requests') as batch:
        batch.alter_column('system_type_id', existing_type=sa.Integer(), nullable=False)
