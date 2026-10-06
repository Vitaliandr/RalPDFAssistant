"""индекс для поиска по словам

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-05
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # выражение как в запросе, иначе индекс не работает
    op.execute("CREATE INDEX chunks_fts_idx ON chunks USING gin (to_tsvector('russian', text))")


def downgrade() -> None:
    op.execute("DROP INDEX chunks_fts_idx")
