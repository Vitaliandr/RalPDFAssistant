"""documents и chunks

Revision ID: 0001
Revises:
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from ralpdfassistant.settings import settings

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("chunks_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    #размер берём из настроек
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(settings.embed_dim), nullable=False),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.execute("CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.drop_table("chunks")
    op.drop_table("documents")
