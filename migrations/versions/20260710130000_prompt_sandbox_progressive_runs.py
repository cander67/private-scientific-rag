"""prompt sandbox progressive runs

Revision ID: 20260710130000
Revises: 20260710120000
Create Date: 2026-07-10 13:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710130000"
down_revision: str | None = "20260710120000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    op.add_column(
        "sandbox_comparisons",
        sa.Column("expected_run_count", sa.Integer(), nullable=False, server_default="0"),
    )
    with op.batch_alter_table(
        "sandbox_runs",
        naming_convention=FK_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.alter_column(
            "prompt_version_id", existing_type=sa.String(length=36), nullable=True
        )
        batch_op.drop_constraint(
            "fk_sandbox_runs_prompt_version_id_sandbox_prompt_versions",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "sandbox_runs_prompt_version_id_fkey",
            "sandbox_prompt_versions",
            ["prompt_version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "sandbox_runs",
        naming_convention=FK_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_sandbox_runs_prompt_version_id_sandbox_prompt_versions",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "sandbox_runs_prompt_version_id_fkey",
            "sandbox_prompt_versions",
            ["prompt_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.alter_column(
            "prompt_version_id", existing_type=sa.String(length=36), nullable=False
        )
    op.drop_column("sandbox_comparisons", "expected_run_count")
