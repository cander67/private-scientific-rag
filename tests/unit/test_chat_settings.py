from __future__ import annotations

import pytest
from pydantic import ValidationError

from private_rag.core.settings import Settings
from private_rag.repositories.schemas import DEFAULT_RAG_CHAT_PROMPT_ID, RepositorySettings


def test_default_repository_settings_include_chat_prompt_library() -> None:
    settings = RepositorySettings.from_app_settings(Settings())

    assert settings.prompt.active_chat_prompt_id == DEFAULT_RAG_CHAT_PROMPT_ID
    assert settings.prompt.active_chat_prompt.id == DEFAULT_RAG_CHAT_PROMPT_ID
    assert "inline citations" in settings.prompt.active_chat_prompt.text


def test_prompt_library_requires_active_prompt_to_exist() -> None:
    settings = RepositorySettings.from_app_settings(Settings()).model_dump(mode="json")
    settings["prompt"]["active_chat_prompt_id"] = "missing"

    with pytest.raises(ValidationError, match="active_chat_prompt_id"):
        RepositorySettings.model_validate(settings)
