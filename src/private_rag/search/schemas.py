from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FullTextSearchFilters(BaseModel):
    document_id: str | None = None
    section: str | None = None
    source_type: str | None = None
    document_kind: str | None = None
    tag: str | None = None


class FullTextSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    filters: FullTextSearchFilters = Field(default_factory=FullTextSearchFilters)


class FullTextRebuildResponse(BaseModel):
    repository_id: str
    indexed_chunks: int
    tokenizer: Literal["unicode61", "porter"]


class FullTextSearchResult(BaseModel):
    rank: int
    score: float
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
    snippet: str
    matched_fields: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class FullTextSearchResponse(BaseModel):
    query: str
    normalized_query: str
    repository_id: str
    results: list[FullTextSearchResult]
