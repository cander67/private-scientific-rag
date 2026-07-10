from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from private_rag.repositories.schemas import PromptLibraryEntry


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
