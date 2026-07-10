from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from private_rag.chat.schemas import ChatCitation, ChatRetrievalSettings
from private_rag.repositories.schemas import PromptLibraryEntry
from private_rag.retrieval.schemas import RetrievalSearchResult


class SandboxPromptVersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    body: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    source_chat_prompt_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_body_or_source(self) -> SandboxPromptVersionCreate:
        if self.body is None and self.source_chat_prompt_id is None:
            raise ValueError("body or source_chat_prompt_id is required")
        return self


class SandboxPromptVersionRead(BaseModel):
    id: str
    repository_id: str
    name: str
    body: str
    notes: str | None
    source_chat_prompt_id: str | None
    used_by_run: bool
    created_at: datetime


class SandboxPromptCopyToChatLibraryRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)


class SandboxPromptCopyToChatLibraryResponse(PromptLibraryEntry):
    pass


class SandboxRunCreate(BaseModel):
    prompt_version_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    model: str = Field(min_length=1)
    retrieval_settings: ChatRetrievalSettings


class SandboxComparisonRunCreate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    prompt_version_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    retrieval_settings: ChatRetrievalSettings


class SandboxComparisonCreate(BaseModel):
    query: str = Field(min_length=1)
    runs: list[SandboxComparisonRunCreate] = Field(min_length=2)


class SandboxRunRead(BaseModel):
    id: str
    repository_id: str
    prompt_version_id: str
    comparison_id: str | None
    comparison_index: int | None
    label: str | None
    query: str
    model: str
    retrieval_settings: ChatRetrievalSettings
    prompt_snapshot: dict[str, object]
    context_entries: list[RetrievalSearchResult]
    retrieval_run_id: str | None
    answer: str
    citations: list[ChatCitation]
    metrics: dict[str, object]
    latency_ms: int
    status: str
    created_at: datetime


class SandboxComparisonRead(BaseModel):
    id: str
    repository_id: str
    query: str
    status: str
    runs: list[SandboxRunRead]
    created_at: datetime
