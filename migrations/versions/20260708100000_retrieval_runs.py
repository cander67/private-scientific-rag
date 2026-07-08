"""retrieval runs

Revision ID: 20260708100000
Revises: 20260707100000
Create Date: 2026-07-08 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260708100000"
down_revision: str | None = "20260707100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retrieval_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("candidate_pool_size", sa.Integer(), nullable=False),
        sa.Column("rrf_constant", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_run_id", sa.String(length=36), nullable=True),
        sa.Column("vector_collection_name", sa.String(length=255), nullable=True),
        sa.Column("reranker_strategy", sa.String(length=80), nullable=False),
        sa.Column("reranker_model", sa.String(length=255), nullable=True),
        sa.Column("metadata_boosts", sa.JSON(), nullable=False),
        sa.Column("settings_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_retrieval_runs_repository_id"),
        "retrieval_runs",
        ["repository_id"],
        unique=False,
    )
    op.create_table(
        "retrieval_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("document_version_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=False),
        sa.Column("source_ranks", sa.JSON(), nullable=False),
        sa.Column("matched_fields", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["retrieval_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_retrieval_results_chunk_id"),
        "retrieval_results",
        ["chunk_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retrieval_results_document_id"),
        "retrieval_results",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retrieval_results_repository_id"),
        "retrieval_results",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retrieval_results_run_id"),
        "retrieval_results",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_retrieval_results_run_id"), table_name="retrieval_results")
    op.drop_index(op.f("ix_retrieval_results_repository_id"), table_name="retrieval_results")
    op.drop_index(op.f("ix_retrieval_results_document_id"), table_name="retrieval_results")
    op.drop_index(op.f("ix_retrieval_results_chunk_id"), table_name="retrieval_results")
    op.drop_table("retrieval_results")
    op.drop_index(op.f("ix_retrieval_runs_repository_id"), table_name="retrieval_runs")
    op.drop_table("retrieval_runs")
