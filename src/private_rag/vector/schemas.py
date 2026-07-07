from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from private_rag.search.schemas import FullTextSearchFilters

VectorSearchFilters = FullTextSearchFilters


class VectorSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    filters: VectorSearchFilters = Field(default_factory=VectorSearchFilters)


class VectorRebuildResponse(BaseModel):
    repository_id: str
    embedding_run_id: str
    provider: Literal["sentence_transformers", "ollama"]
    model: str
    collection_name: str
    indexed_chunks: int
    vector_size: int
    distance: Literal["cosine", "dot", "euclid"]


class VectorSearchResult(BaseModel):
    rank: int
    score: float
    distance: Literal["cosine", "dot", "euclid"]
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
    text_preview: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding_run_id: str
    embedding_provider: str
    embedding_model: str
    vector_size: int
    collection_name: str


class VectorSearchResponse(BaseModel):
    query: str
    repository_id: str
    embedding_run_id: str
    provider: str
    model: str
    collection_name: str
    vector_size: int
    distance: str
    results: list[VectorSearchResult]
