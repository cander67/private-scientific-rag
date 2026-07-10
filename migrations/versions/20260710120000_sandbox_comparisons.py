"""sandbox comparisons

Revision ID: 20260710120000
Revises: 20260710110000
Create Date: 2026-07-10 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710120000"
down_revision: str | None = "20260710110000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sandbox_comparisons",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sandbox_comparisons_repository_id"),
        "sandbox_comparisons",
        ["repository_id"],
    )
    op.add_column("sandbox_runs", sa.Column("comparison_id", sa.String(length=36), nullable=True))
    op.add_column("sandbox_runs", sa.Column("comparison_index", sa.Integer(), nullable=True))
    op.add_column("sandbox_runs", sa.Column("label", sa.String(length=120), nullable=True))
    op.create_index(
        op.f("ix_sandbox_runs_comparison_id"),
        "sandbox_runs",
        ["comparison_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sandbox_runs_comparison_id"), table_name="sandbox_runs")
    op.drop_column("sandbox_runs", "label")
    op.drop_column("sandbox_runs", "comparison_index")
    op.drop_column("sandbox_runs", "comparison_id")
    op.drop_index(
        op.f("ix_sandbox_comparisons_repository_id"),
        table_name="sandbox_comparisons",
    )
    op.drop_table("sandbox_comparisons")
