from __future__ import annotations

import pytest
from pydantic import ValidationError

from private_rag.core.settings import Settings
from private_rag.repositories.schemas import (
    RecreateValidationRequest,
    RepositorySettings,
)
from private_rag.repositories.service import validate_recreate_request


def test_default_repository_settings_use_app_model_defaults() -> None:
    app_settings = Settings(
        default_llm="llama3.2:3b",
        default_embedding_model="sentence-transformers/test-embedding",
        default_reranker="cross-encoder/test-reranker",
    )

    repository_settings = RepositorySettings.from_app_settings(app_settings)

    assert repository_settings.model.ollama_chat_model == "llama3.2:3b"
    assert repository_settings.embedding.model == "sentence-transformers/test-embedding"
    assert repository_settings.reranking.model == "cross-encoder/test-reranker"


def test_repository_settings_reject_chunk_overlap_larger_than_chunk_size() -> None:
    app_settings = Settings()
    payload = RepositorySettings.from_app_settings(app_settings).model_dump(mode="json")
    payload["chunking"] = {"chunk_size": 500, "chunk_overlap": 500, "mode": "recursive"}

    with pytest.raises(ValidationError, match="chunk_overlap must be smaller"):
        RepositorySettings.model_validate(payload)


def test_recreate_validation_reports_missing_files_and_models(tmp_path) -> None:
    existing_source = tmp_path / "paper.pdf"
    existing_source.write_text("source", encoding="utf-8")
    settings = RepositorySettings.from_app_settings(Settings())
    manifest = {
        "repository": {
            "id": "repo-1",
            "name": "Default Repository",
            "root_path": str(tmp_path),
            "created_at": "2026-06-30T00:00:00Z",
            "updated_at": "2026-06-30T00:00:00Z",
        },
        "settings": settings.model_dump(mode="json"),
        "source_files": [str(existing_source), str(tmp_path / "missing.pdf")],
    }
    request = RecreateValidationRequest.model_validate(
        {
            "manifest": manifest,
            "available_models": [settings.embedding.model],
        }
    )

    result = validate_recreate_request(request)

    assert result.can_recreate is False
    assert [issue.code for issue in result.missing_source_files] == ["missing_source_file"]
    assert {issue.message for issue in result.missing_models} == {
        f"Required model is not available: {settings.model.ollama_chat_model}",
        f"Required model is not available: {settings.reranking.model}",
    }
