from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal["pdf", "text", "markdown", "annotation"]
DocumentStatus = Literal["parsed", "needs_ocr", "failed", "skipped"]


class DocumentChunkRead(BaseModel):
    id: str
    repository_id: str
    document_id: str
    document_version_id: str
    chunk_index: int
    text: str
    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    parser_version: str
    source_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PageImageRead(BaseModel):
    page: int
    url: str
    mime_type: str = "image/png"
    width: int | None = None
    height: int | None = None
    byte_size: int
    sha256: str


class DocumentVersionRead(BaseModel):
    id: str
    document_id: str
    repository_id: str
    original_filename: str
    content_type: str | None = None
    source_type: SourceType
    sha256: str
    byte_size: int
    storage_path: str
    status: DocumentStatus
    parser_name: str
    parser_version: str
    ocr_required: bool
    page_count: int | None = None
    line_count: int | None = None
    section_count: int
    chunk_count: int
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DocumentRead(BaseModel):
    id: str
    repository_id: str
    display_name: str
    current_version_id: str | None = None
    created_at: datetime
    updated_at: datetime
    current_version: DocumentVersionRead | None = None


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
    version: DocumentVersionRead
    chunks_preview: list[DocumentChunkRead] = Field(default_factory=list)


class DocumentInspection(BaseModel):
    document: DocumentRead
    version: DocumentVersionRead
    chunks: list[DocumentChunkRead] = Field(default_factory=list)
    page_images: list[PageImageRead] = Field(default_factory=list)


class ParsedSegment(BaseModel):
    text: str
    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    source_type: SourceType
    text: str
    parser_name: str = "private-rag-built-in"
    parser_version: str = "prd3-v1"
    segments: list[ParsedSegment] = Field(default_factory=list)
    page_count: int | None = None
    line_count: int | None = None
    sections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    ocr_required: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
