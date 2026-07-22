from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from private_rag.chat.llm import ChatModelInfo
from private_rag.retrieval.schemas import RerankerStrategy, RetrievalDefaults, RetrievalMode

ChatRole = Literal["user", "assistant"]
ChatReadinessStatus = Literal[
    "not_checked",
    "unavailable_runtime",
    "not_installed",
    "ready",
    "failed",
    "missing",
    "partial",
    "stale",
]


class ChatRetrievalSettings(RetrievalDefaults):
    mode: RetrievalMode = "hybrid"
    top_k: int = Field(default=6, ge=1, le=50)
    reranker_strategy: RerankerStrategy = "cross_encoder"


class ChatCitation(BaseModel):
    citation_id: int
    token: str
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
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieval_rank: int
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    text_preview: str | None = None


class ChatMessageRead(BaseModel):
    id: str
    session_id: str
    sequence: int
    role: ChatRole
    content: str
    retrieval_run_id: str | None = None
    citations: list[ChatCitation] = Field(default_factory=list)
    created_at: datetime


class ChatSessionRead(BaseModel):
    id: str
    repository_id: str
    title: str
    model: str
    retrieval_settings: ChatRetrievalSettings
    prompt_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageRead] = Field(default_factory=list)


class ChatSessionCreate(BaseModel):
    title: str | None = None
    model: str | None = None
    retrieval_settings: ChatRetrievalSettings | None = None


class ChatQuestionRequest(BaseModel):
    content: str = Field(min_length=1)
    retrieval_settings: ChatRetrievalSettings | None = None


class ChatQuestionResponse(BaseModel):
    session: ChatSessionRead
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead


class ChatModelRegistryResponse(BaseModel):
    default_model: str
    models: list[ChatModelInfo]


class ChatModelSmokeResponse(BaseModel):
    model: str
    ok: bool
    response: str


class ChatReadinessItem(BaseModel):
    ready: bool
    status: ChatReadinessStatus
    message: str
    indexed_chunks: int | None = None
    model: str | None = None


class ChatReadinessResponse(BaseModel):
    repository_id: str
    parsed_chunks: int
    full_text: ChatReadinessItem
    vector: ChatReadinessItem
    local_model: ChatReadinessItem
    ready_for_chat: bool
