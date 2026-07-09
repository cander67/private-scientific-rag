from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from private_rag.chat.llm import ChatModelInfo

ChatRole = Literal["user", "assistant"]


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
    retrieval_settings: dict[str, Any]
    prompt_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageRead] = Field(default_factory=list)


class ChatSessionCreate(BaseModel):
    title: str | None = None
    model: str | None = None


class ChatQuestionRequest(BaseModel):
    content: str = Field(min_length=1)


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
