"""SVT installed security controls, MNI and ZMNI with container issuance history."""
from alembic import op
import sqlalchemy as sa

revision = '0011_svt_media_protection'
down_revision = '0010_oi_reviews'
branch_labels = None
depends_on = None

def upgrade():
    bind=op.get_bind()
    existing_tables=set(sa.inspect(bind).get_table_names())
    existing_columns={c['name'] for c in sa.inspect(bind).get_columns('assets')}
    for name, length in [('savz_name',200),('savz_version',120),('szi_nsd_name',200),('szi_nsd_version',120)]:
        if name not in existing_columns:
            op.add_column('assets', sa.Column(name,sa.String(length),nullable=False,server_default=''))
    if 'asset_mni' not in existing_tables:
        op.create_table('asset_mni',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('asset_id',sa.Integer(),sa.ForeignKey('assets.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('serial_number',sa.String(150),nullable=False),
        sa.Column('accounting_number',sa.String(150),nullable=False),
        sa.Column('media_type',sa.String(60),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('asset_id','serial_number',name='uq_asset_mni_serial'))
    if 'ix_asset_mni_accounting' not in {x['name'] for x in sa.inspect(bind).get_indexes('asset_mni')}:
        op.create_index('ix_asset_mni_accounting','asset_mni',['accounting_number'])
    if 'asset_zmni' not in existing_tables:
        op.create_table('asset_zmni',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('asset_id',sa.Integer(),sa.ForeignKey('assets.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('serial_number',sa.String(150),nullable=False),
        sa.Column('accounting_number',sa.String(150),nullable=False),
        sa.Column('software_version',sa.String(120),nullable=False,server_default=''),
        sa.Column('container_filename',sa.String(255),nullable=False,server_default=''),
        sa.Column('container_issued_on',sa.Date(),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('asset_id','serial_number',name='uq_asset_zmni_serial'))
    if 'software_version' not in {c['name'] for c in sa.inspect(bind).get_columns('asset_zmni')}:
        op.add_column('asset_zmni',sa.Column('software_version',sa.String(120),nullable=False,server_default=''))
    if 'ix_asset_zmni_accounting' not in {x['name'] for x in sa.inspect(bind).get_indexes('asset_zmni')}:
        op.create_index('ix_asset_zmni_accounting','asset_zmni',['accounting_number'])
    if 'zmni_container_history' not in existing_tables:
        op.create_table('zmni_container_history',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('zmni_id',sa.Integer(),sa.ForeignKey('asset_zmni.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('container_filename',sa.String(255),nullable=False),
        sa.Column('container_issued_on',sa.Date(),nullable=True),
        sa.Column('recorded_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False))
    if 'ix_zmni_container_history' not in {x['name'] for x in sa.inspect(bind).get_indexes('zmni_container_history')}:
        op.create_index('ix_zmni_container_history','zmni_container_history',['zmni_id','recorded_at'])

def downgrade():
    bind = op.get_bind()
    for name in ('asset_mni','asset_zmni','zmni_container_history'):
        if bind.execute(sa.text('SELECT count(*) FROM '+name)).scalar_one():
            raise RuntimeError('Downgrade with tracked media is unsafe: '+name)
    op.drop_index('ix_zmni_container_history',table_name='zmni_container_history')
    op.drop_table('zmni_container_history')
    op.drop_index('ix_asset_zmni_accounting',table_name='asset_zmni')
    op.drop_table('asset_zmni')
    op.drop_index('ix_asset_mni_accounting',table_name='asset_mni')
    op.drop_table('asset_mni')
    for name in ('savz_name','savz_version','szi_nsd_name','szi_nsd_version'):
        op.drop_column('assets',name)
