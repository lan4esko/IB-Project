"""GIN Russian full-text index on existing document content.

Revision ID: 0005_russian_fts
Revises: 0004_rag_chunks
"""
from alembic import op

revision = "0005_russian_fts"
down_revision = "0004_rag_chunks"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE INDEX IF NOT EXISTS ix_document_chunks_content_fts_ru
            ON document_chunks USING GIN
            (to_tsvector('russian', coalesce(content, '')))""")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_fts_ru")
