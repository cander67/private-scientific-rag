from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from private_rag.search.schemas import FullTextSearchFilters

RetrievalMode = Literal["full_text", "vector", "hybrid"]
RerankerStrategy = Literal[
    "none", "cross_encoder", "metadata_boost", "cross_encoder_metadata_boost"
]
BoostLevel = Literal["off", "low", "medium", "high"]
RetrievalSettingsSource = Literal[
    "fallback_defaults",
    "repository_defaults",
    "session_defaults",
    "run_override",
]


class MetadataBoostSettings(BaseModel):
    section: BoostLevel = "medium"
    patent_section: BoostLevel = "medium"
    document_kind: BoostLevel = "low"
    table_figure: BoostLevel = "low"


class RetrievalDefaults(BaseModel):
    mode: RetrievalMode = "full_text"
    top_k: int = Field(default=10, ge=1, le=50)
    candidate_pool_size: int | None = Field(default=None, ge=1, le=250)
    rrf_constant: int = Field(default=60, ge=1, le=1000)
    reranker_strategy: RerankerStrategy = "none"
    metadata_boosts: MetadataBoostSettings = Field(default_factory=MetadataBoostSettings)
    filters: FullTextSearchFilters = Field(default_factory=FullTextSearchFilters)


class RepositoryRetrievalSettings(RetrievalDefaults):
    mode: RetrievalMode = "hybrid"
    top_k: int = Field(default=6, ge=1, le=50)
    reranker_strategy: RerankerStrategy = "cross_encoder"


class RetrievalSearchRequest(RetrievalDefaults):
    query: str = Field(min_length=1)


class EffectiveRetrievalSettings(BaseModel):
    settings: RetrievalDefaults
    sources: dict[str, RetrievalSettingsSource]


class RetrievalSearchResult(BaseModel):
    rank: int
    final_score: float
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    source_ranks: dict[str, int | None] = Field(default_factory=dict)
    repository_id: str
    document_id: str
    document_version_id: str
    chunk_id: str
    chunk_index: int
    document_title: str
    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    snippet: str | None = None
    text_preview: str | None = None
    matched_fields: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding_run_id: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    vector_size: int | None = None
    collection_name: str | None = None


class RetrievalSearchResponse(BaseModel):
    run_id: str
    query: str
    repository_id: str
    mode: RetrievalMode
    top_k: int
    candidate_pool_size: int
    rrf_constant: int
    reranker_strategy: RerankerStrategy
    results: list[RetrievalSearchResult]
