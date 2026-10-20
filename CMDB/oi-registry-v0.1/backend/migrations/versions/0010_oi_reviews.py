"""OI reviews: reports and individually resolved deficiencies / violations."""
from alembic import op
import sqlalchemy as sa

revision = '0010_oi_reviews'
down_revision = '0009_requests_no_type'
branch_labels = None
depends_on = None

def upgrade():
    bind=op.get_bind()
    tables=set(sa.inspect(bind).get_table_names())
    if 'oi_reviews' not in tables:
        op.create_table('oi_reviews',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('oi_id', sa.Integer(), sa.ForeignKey('information_objects.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reviewed_on', sa.Date(), nullable=False),
        sa.Column('reviewer', sa.String(180), nullable=False),
        sa.Column('report_smb_path', sa.Text(), nullable=False, server_default=''),
        sa.Column('notes', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    if 'ix_oi_reviews_object_date' not in {x['name'] for x in sa.inspect(bind).get_indexes('oi_reviews')}:
        op.create_index('ix_oi_reviews_object_date', 'oi_reviews', ['oi_id','reviewed_on'])
    if 'oi_review_findings' not in tables:
        op.create_table('oi_review_findings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('review_id', sa.Integer(), sa.ForeignKey('oi_reviews.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('corrective_action', sa.Text(), nullable=False, server_default=''),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    if 'ix_oi_finding_review_status' not in {x['name'] for x in sa.inspect(bind).get_indexes('oi_review_findings')}:
        op.create_index('ix_oi_finding_review_status', 'oi_review_findings', ['review_id','resolved'])

def downgrade():
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT count(*) FROM oi_reviews')).scalar_one() or bind.execute(sa.text('SELECT count(*) FROM oi_review_findings')).scalar_one():
        raise RuntimeError('Cannot downgrade inspections with existing records')
    op.drop_index('ix_oi_finding_review_status', table_name='oi_review_findings')
    op.drop_table('oi_review_findings')
    op.drop_index('ix_oi_reviews_object_date', table_name='oi_reviews')
    op.drop_table('oi_reviews')
