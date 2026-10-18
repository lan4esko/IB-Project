"""Asset hardware, MFP access, repairs and quarterly infosec inspections."""
from alembic import op
import sqlalchemy as sa
from app.models import (AssetComponent, SharedPeripheral, AssetPeripheralAccess,
                        AssetSecurityTool, ServiceRequest, WorkEntry, AssetInspection)

revision = "0003_asset_lifecycle"
down_revision = "0002_configuration"
branch_labels = None
depends_on = None

def upgrade():
    bind=op.get_bind()
    columns = {x["name"] for x in sa.inspect(bind).get_columns("assets")}
    for name, width, default in (("hostname", 250, ""), ("domain_name", 250, ""),
                                  ("seal_state", 36, "unknown")):
        if name not in columns:
            op.add_column("assets", sa.Column(name, sa.String(width), nullable=False, server_default=default))
    for table in (AssetComponent, SharedPeripheral, AssetPeripheralAccess, AssetSecurityTool,
                  ServiceRequest, WorkEntry, AssetInspection):
        table.__table__.create(bind, checkfirst=True)

def downgrade():
    bind=op.get_bind()
    for table in (AssetInspection, WorkEntry, ServiceRequest, AssetSecurityTool,
                  AssetPeripheralAccess, SharedPeripheral, AssetComponent):
        table.__table__.drop(bind, checkfirst=True)
    for column in ("seal_state", "domain_name", "hostname"):
        op.drop_column("assets", column)
