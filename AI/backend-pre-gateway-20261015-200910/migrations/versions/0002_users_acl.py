"""Auth and object ACL on top of normative registries.
Revision ID: 0002_users_acl
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_users_acl"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "users", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(300), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_users_username", "users", ["username"])
    op.create_table(
        "user_sessions", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_table(
        "object_grants", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("object_id", sa.Integer(), sa.ForeignKey("info_objects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("object_id", "user_id", name="uq_object_grant"))
    op.create_index("ix_object_grants_object_id", "object_grants", ["object_id"])
    op.create_index("ix_object_grants_user_id", "object_grants", ["user_id"])
    op.add_column("audit_events", sa.Column("actor_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_audit_actor", "audit_events", "users", ["actor_user_id"], ["id"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])

def downgrade():
    raise RuntimeError("Downgrade 0002 отключён: необходимо восстановление из резервной копии")
