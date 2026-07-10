from __future__ import annotations

import pytest
from pydantic import ValidationError

from private_rag.prompt_sandbox.schemas import SandboxPromptVersionCreate


def test_sandbox_prompt_create_requires_body_or_chat_prompt_source() -> None:
    with pytest.raises(ValidationError, match="body or source_chat_prompt_id is required"):
        SandboxPromptVersionCreate(name="No source")


def test_sandbox_prompt_create_accepts_direct_body() -> None:
    request = SandboxPromptVersionCreate(name="Direct prompt", body="Answer with citations.")

    assert request.name == "Direct prompt"
    assert request.body == "Answer with citations."
    assert request.source_chat_prompt_id is None


def test_sandbox_prompt_create_accepts_chat_prompt_source() -> None:
    request = SandboxPromptVersionCreate(
        name="Copied prompt",
        source_chat_prompt_id="rag-chat-default-v1",
    )

    assert request.name == "Copied prompt"
    assert request.body is None
    assert request.source_chat_prompt_id == "rag-chat-default-v1"
