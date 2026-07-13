"""prompt sandbox

Revision ID: 20260710100000
Revises: 20260709120000
Create Date: 2026-07-10 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710100000"
down_revision: str | None = "20260709120000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sandbox_prompt_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_chat_prompt_id", sa.String(length=120), nullable=True),
        sa.Column("used_by_run", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sandbox_prompt_versions_repository_id"),
        "sandbox_prompt_versions",
        ["repository_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_sandbox_prompt_versions_repository_id"),
        table_name="sandbox_prompt_versions",
    )
    op.drop_table("sandbox_prompt_versions")
