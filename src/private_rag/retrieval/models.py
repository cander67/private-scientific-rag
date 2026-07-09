from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from private_rag.db.base import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class RetrievalRun(Base):
    __tablename__ = "retrieval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_pool_size: Mapped[int] = mapped_column(Integer, nullable=False)
    rrf_constant: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    vector_collection_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reranker_strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    reranker_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_boosts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    settings_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    results: Mapped[list[RetrievalResult]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="RetrievalResult.rank",
    )


class RetrievalResult(Base):
    __tablename__ = "retrieval_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    document_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[float] = mapped_column(nullable=False)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_ranks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    matched_fields: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    result_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    run: Mapped[RetrievalRun] = relationship(back_populates="results")
