from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from private_rag.chat.llm import ChatCompletion, ChatMessage, OllamaUnavailableError
from private_rag.core.settings import Settings
from private_rag.repositories.schemas import (
    RecreateValidationRequest,
    RepositorySettings,
)
from private_rag.repositories.service import (
    LocalSettingsReadinessChecker,
    analyze_settings_impact,
    validate_recreate_request,
)


class _MissingChatModelLLM:
    def complete(
        self, *, model: str, messages: list[ChatMessage]
    ) -> ChatCompletion:  # pragma: no cover
        raise NotImplementedError

    def smoke(self, *, model: str) -> ChatCompletion:
        raise OllamaUnavailableError(
            f"Ollama model '{model}' is not installed. Run `ollama pull {model}`.",
            readiness_status="not_installed",
        )


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


def test_repository_settings_reject_cross_encoder_without_model() -> None:
    app_settings = Settings()
    payload = RepositorySettings.from_app_settings(app_settings).model_dump(mode="json")
    payload["reranking"] = {"strategy": "cross_encoder", "model": None}

    with pytest.raises(ValidationError, match="reranking.model is required"):
        RepositorySettings.model_validate(payload)


def test_repository_settings_reject_ollama_dot_distance() -> None:
    app_settings = Settings()
    payload = RepositorySettings.from_app_settings(app_settings).model_dump(mode="json")
    payload["embedding"]["provider"] = "ollama"
    payload["embedding"]["model"] = "embeddinggemma:300m"
    payload["vector"]["vector_size"] = 768
    payload["vector"]["distance"] = "dot"

    with pytest.raises(ValidationError, match="does not support distance"):
        RepositorySettings.model_validate(payload)


def test_repository_settings_accept_custom_ollama_model_pending_live_probe() -> None:
    app_settings = Settings()
    payload = RepositorySettings.from_app_settings(app_settings).model_dump(mode="json")
    payload["embedding"]["provider"] = "ollama"
    payload["embedding"]["model"] = "nomic-embed-text:custom"
    payload["vector"]["vector_size"] = 768

    settings = RepositorySettings.model_validate(payload)

    assert settings.embedding.model == "nomic-embed-text:custom"


def test_repository_settings_accept_custom_sentence_transformers_model() -> None:
    app_settings = Settings()
    payload = RepositorySettings.from_app_settings(app_settings).model_dump(mode="json")
    payload["embedding"]["model"] = "sentence-transformers/not-approved"

    settings = RepositorySettings.model_validate(payload)

    assert settings.embedding.model == "sentence-transformers/not-approved"


def test_repository_settings_reject_known_embedding_vector_size_mismatch() -> None:
    app_settings = Settings()
    payload = RepositorySettings.from_app_settings(app_settings).model_dump(mode="json")
    payload["embedding"]["model"] = "sentence-transformers/all-mpnet-base-v2"
    payload["vector"]["vector_size"] = 384

    with pytest.raises(ValidationError, match="expects vector size 768"):
        RepositorySettings.model_validate(payload)


def test_repository_settings_reject_invalid_active_prompt() -> None:
    app_settings = Settings()
    payload = RepositorySettings.from_app_settings(app_settings).model_dump(mode="json")
    payload["prompt"]["active_chat_prompt_id"] = "missing-prompt"

    with pytest.raises(ValidationError, match="active_chat_prompt_id"):
        RepositorySettings.model_validate(payload)


def test_settings_impact_reports_reprocessing_and_index_rebuilds() -> None:
    current = RepositorySettings.from_app_settings(Settings())
    draft_payload = current.model_dump(mode="json")
    draft_payload["chunking"]["chunk_size"] = 1200
    draft_payload["full_text"]["tokenizer"] = "porter"
    draft_payload["embedding"]["model"] = "sentence-transformers/other"
    draft = RepositorySettings.model_validate(draft_payload)

    result = analyze_settings_impact(current, draft)

    categories = {impact.category for impact in result.impacts}
    assert result.has_changes is True
    assert "document_reprocessing" in categories
    assert "full_text_rebuild" in categories
    assert "vector_rebuild" in categories
    assert "export_recreate" in categories
    assert "evaluation_freshness" in categories


def test_settings_impact_reports_retrieval_chat_and_prompt_defaults() -> None:
    current = RepositorySettings.from_app_settings(Settings())
    draft_payload = current.model_dump(mode="json")
    draft_payload["reranking"]["model"] = "cross-encoder/new"
    draft_payload["model"]["ollama_chat_model"] = "llama3.2:latest"
    draft_payload["prompt"]["library"][0]["text"] = "Answer carefully from context."
    draft = RepositorySettings.model_validate(draft_payload)

    result = analyze_settings_impact(current, draft)

    categories = {impact.category for impact in result.impacts}
    assert "retrieval_defaults" in categories
    assert "chat_defaults" in categories
    assert "prompt_defaults" in categories
    assert "evaluation_freshness" in categories


def test_settings_impact_reports_no_changes_for_same_settings() -> None:
    current = RepositorySettings.from_app_settings(Settings())

    result = analyze_settings_impact(current, current)

    assert result.has_changes is False
    assert result.impacts == []


def test_readiness_checker_skips_disabled_reranker() -> None:
    checker = LocalSettingsReadinessChecker()

    result = checker.check_reranker(strategy="none", model=None)

    assert result.target == "reranker"
    assert result.status == "skipped"
    assert result.ready is True
    assert "disabled" in result.message


def test_readiness_checker_reports_missing_chat_model_with_pull_guidance() -> None:
    checker = LocalSettingsReadinessChecker()

    result = checker.check_chat(llm=_MissingChatModelLLM(), model="custom-local:latest")

    assert result.target == "chat"
    assert result.status == "not_installed"
    assert result.ready is False
    assert "ollama pull custom-local:latest" in result.message


def test_recreate_validation_reports_missing_files_and_models(tmp_path: Path) -> None:
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
