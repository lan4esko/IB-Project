"""OI attestation dates, peripheral media/drivers, identity, audit, submissions."""
from alembic import op
import sqlalchemy as sa
from app.models import OIProposal

revision = '0004_governance'
down_revision = '0003_asset_lifecycle'
branch_labels = None
depends_on = None

def add(table, name, typ, default=None):
    existing={c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}
    if name in existing: return
    col=sa.Column(name, typ, nullable=True if default is None else False, server_default=default)
    op.add_column(table,col)

def upgrade():
    add('users','display_name',sa.String(180),'')
    add('users','must_change_password',sa.Boolean(),sa.false())
    add('users','created_by',sa.Integer())
    add('information_objects','attestation_issued_on',sa.Date())
    add('information_objects','attestation_valid_until',sa.Date())
    add('information_objects','attestation_document_id',sa.Integer())
    add('information_objects','attestation_notice_days',sa.Integer(),'90')
    for name,typ in [('manufacturer',sa.String(150)),('model',sa.String(200)),('inventory_number',sa.String(150)),('media_kind',sa.String(100)),('media_serial_number',sa.String(150)),('media_inventory_number',sa.String(150))]:
        add('shared_peripherals',name,typ,'')
    add('shared_peripherals','media_present',sa.Boolean(),sa.false())
    for name,typ in [('connection_type',sa.String(32)),('driver_name',sa.String(250)),('driver_version',sa.String(120)),('driver_smb_path',sa.String(700)),('driver_sha256',sa.String(64))]:
        add('asset_peripheral_access',name,typ,'lan' if name=='connection_type' else '')
    add('asset_peripheral_access','driver_document_id',sa.Integer())
    add('audit_events','request_id',sa.String(36),'')
    add('audit_events','source_ip',sa.String(60),'')
    add('audit_events','user_agent',sa.String(256),'')
    OIProposal.__table__.create(op.get_bind(),checkfirst=True)
    if not any(i['name']=='ix_oi_attestation_expiry' for i in sa.inspect(op.get_bind()).get_indexes('information_objects')):
        op.create_index('ix_oi_attestation_expiry','information_objects',['attestation_valid_until'])

def downgrade():
    op.drop_index('ix_oi_attestation_expiry',table_name='information_objects')
    OIProposal.__table__.drop(op.get_bind(),checkfirst=True)
    for table,cols in {
      'audit_events':['user_agent','source_ip','request_id'],
      'asset_peripheral_access':['driver_document_id','driver_sha256','driver_smb_path','driver_version','driver_name','connection_type'],
      'shared_peripherals':['media_present','media_inventory_number','media_serial_number','media_kind','inventory_number','model','manufacturer'],
      'information_objects':['attestation_notice_days','attestation_document_id','attestation_valid_until','attestation_issued_on'],
      'users':['created_by','must_change_password','display_name'],
    }.items():
        for col in cols: op.drop_column(table,col)
