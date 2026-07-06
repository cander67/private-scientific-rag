"""full text search

Revision ID: 20260706120000
Revises: 20260701101500
Create Date: 2026-07-06 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260706120000"
down_revision: str | None = "20260701101500"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS full_text_chunks USING fts5(
            repository_id UNINDEXED,
            document_id UNINDEXED,
            document_version_id UNINDEXED,
            chunk_id UNINDEXED,
            chunk_index UNINDEXED,
            document_title UNINDEXED,
            section UNINDEXED,
            source_type UNINDEXED,
            document_kind UNINDEXED,
            tags UNINDEXED,
            page_start UNINDEXED,
            page_end UNINDEXED,
            line_start UNINDEXED,
            line_end UNINDEXED,
            title,
            headings,
            body,
            captions,
            tables,
            claims,
            examples,
            tokenize = 'unicode61',
            prefix='2 3 4'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS full_text_chunks")
