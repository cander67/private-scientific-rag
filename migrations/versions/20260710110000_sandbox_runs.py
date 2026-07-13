"""sandbox runs

Revision ID: 20260710110000
Revises: 20260710100000
Create Date: 2026-07-10 11:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710110000"
down_revision: str | None = "20260710100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sandbox_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("prompt_version_id", sa.String(length=36), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("retrieval_settings", sa.JSON(), nullable=False),
        sa.Column("prompt_snapshot", sa.JSON(), nullable=False),
        sa.Column("context_entries", sa.JSON(), nullable=False),
        sa.Column("retrieval_run_id", sa.String(length=36), nullable=True),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"], ["sandbox_prompt_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sandbox_runs_prompt_version_id"), "sandbox_runs", ["prompt_version_id"]
    )
    op.create_index(op.f("ix_sandbox_runs_repository_id"), "sandbox_runs", ["repository_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_sandbox_runs_repository_id"), table_name="sandbox_runs")
    op.drop_index(op.f("ix_sandbox_runs_prompt_version_id"), table_name="sandbox_runs")
    op.drop_table("sandbox_runs")
