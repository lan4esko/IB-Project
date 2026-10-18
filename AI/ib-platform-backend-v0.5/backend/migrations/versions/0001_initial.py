"""Первичная схема реестров ИБ-платформы для PostgreSQL.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "normative_acts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("revision", sa.String(length=100), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("source_uri", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", "revision", name="uq_act_code_revision"),
    )
    op.create_index("ix_normative_acts_code", "normative_acts", ["code"])
    op.create_table(
        "info_objects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("stage", sa.String(length=60), nullable=False),
        sa.Column("owner", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("act_id", sa.Integer(), sa.ForeignKey("normative_acts.id"), nullable=False),
        sa.Column("clause", sa.String(length=160), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("applicability", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_requirements_act_id", "requirements", ["act_id"])
    op.create_table(
        "measures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("requirements.id"), nullable=False),
        sa.Column("info_object_id", sa.Integer(), sa.ForeignKey("info_objects.id"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=200), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("evidence_uri", sa.String(length=1000), nullable=True),
        sa.Column("reviewed_by", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_measures_requirement_id", "measures", ["requirement_id"])
    op.create_index("ix_measures_info_object_id", "measures", ["info_object_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

def downgrade():
    # Удаление таблиц вместе с содержимым нельзя считать безопасным rollback.
    raise RuntimeError("Downgrade 0001 запрещён: восстановите данные из резервной копии")
