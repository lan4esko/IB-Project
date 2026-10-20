"""Nullable SVT membership; SMB attestation references; independent request register."""
from alembic import op
import sqlalchemy as sa
from app.models import RegistryRequest, SystemType

revision = '0008_registry_v061'
down_revision = '0007_oi_transfer_approvals'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    info = sa.inspect(bind)
    names = {c['name'] for c in info.get_columns('information_objects')}
    if 'attestation_smb_path' not in names:
        op.add_column('information_objects', sa.Column('attestation_smb_path', sa.Text(),
                                                       nullable=False, server_default=''))
    asset_column = next(c for c in info.get_columns('assets') if c['name'] == 'oi_id')
    if not asset_column['nullable']:
        with op.batch_alter_table('assets') as batch:
            batch.alter_column('oi_id', existing_type=sa.Integer(), nullable=True)
    SystemType.__table__.create(bind, checkfirst=True)
    RegistryRequest.__table__.create(bind, checkfirst=True)


def downgrade():
    # Refuse destructive downgrade if standalone SVT or administrative requests exist.
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT count(*) FROM assets WHERE oi_id IS NULL')).scalar_one():
        raise RuntimeError('Assign every standalone SVT to an OI before downgrade')
    if bind.execute(sa.text('SELECT count(*) FROM registry_requests')).scalar_one():
        raise RuntimeError('Archive registry_requests before downgrade')
    RegistryRequest.__table__.drop(bind, checkfirst=True)
    SystemType.__table__.drop(bind, checkfirst=True)
    with op.batch_alter_table('assets') as batch:
        batch.alter_column('oi_id', existing_type=sa.Integer(), nullable=False)
    op.drop_column('information_objects', 'attestation_smb_path')
