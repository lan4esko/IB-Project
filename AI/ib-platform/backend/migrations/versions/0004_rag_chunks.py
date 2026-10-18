"""Document chunk storage for small pilot RAG.

Revision ID: 0004_rag_chunks
Revises: 0003_documents
"""
from alembic import op
import sqlalchemy as sa
revision = "0004_rag_chunks"
down_revision = "0003_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_version_id", sa.Integer(), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("embedding_json", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_version_id", "chunk_index", name="uq_document_chunk_version_order"))
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_document_version_id", "document_chunks", ["document_version_id"])


def downgrade():
    raise RuntimeError("Откат 0004 не поддерживается: восстановите проверенный бэкап")
