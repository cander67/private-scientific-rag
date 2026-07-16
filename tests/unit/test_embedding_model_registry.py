from __future__ import annotations

import pytest

from private_rag.vector.model_registry import (
    EmbeddingModelCompatibilityError,
    is_custom_ollama_embedding_model,
    known_embedding_models,
    validate_embedding_model_settings,
)


def test_known_embedding_models_include_prd15_models() -> None:
    registry = {(model.provider, model.model): model for model in known_embedding_models()}

    assert (
        registry[("sentence_transformers", "sentence-transformers/all-MiniLM-L6-v2")].vector_size
        == 384
    )
    assert (
        registry[("sentence_transformers", "sentence-transformers/all-mpnet-base-v2")].vector_size
        == 768
    )
    assert registry[("ollama", "embeddinggemma:300m")].vector_size == 768
    assert registry[("ollama", "qwen3-embedding:8b")].vector_size == 4096


def test_lookup_rejects_provider_model_mismatch() -> None:
    with pytest.raises(EmbeddingModelCompatibilityError, match="belongs to provider"):
        validate_embedding_model_settings(
            provider="ollama",
            model="sentence-transformers/all-mpnet-base-v2",
            vector_size=768,
            distance="cosine",
        )


def test_validate_rejects_unsupported_distance_for_known_ollama_model() -> None:
    with pytest.raises(EmbeddingModelCompatibilityError, match="does not support distance"):
        validate_embedding_model_settings(
            provider="ollama",
            model="embeddinggemma:300m",
            vector_size=768,
            distance="dot",
        )


def test_validate_rejects_known_model_vector_size_mismatch() -> None:
    with pytest.raises(EmbeddingModelCompatibilityError, match="expects vector size 768"):
        validate_embedding_model_settings(
            provider="sentence_transformers",
            model="sentence-transformers/all-mpnet-base-v2",
            vector_size=384,
            distance="cosine",
        )


def test_custom_ollama_model_requires_live_probe() -> None:
    assert is_custom_ollama_embedding_model("ollama", "nomic-embed-text:custom") is True

    with pytest.raises(EmbeddingModelCompatibilityError, match="live dimension probe"):
        validate_embedding_model_settings(
            provider="ollama",
            model="nomic-embed-text:custom",
            vector_size=768,
            distance="cosine",
        )


def test_custom_ollama_model_accepts_matching_probe_dimension() -> None:
    result = validate_embedding_model_settings(
        provider="ollama",
        model="nomic-embed-text:custom",
        vector_size=768,
        distance="cosine",
        probed_vector_size=768,
    )

    assert result is None


def test_custom_sentence_transformers_model_accepts_matching_probe_dimension() -> None:
    result = validate_embedding_model_settings(
        provider="sentence_transformers",
        model="sentence-transformers/test-embedding",
        vector_size=384,
        distance="cosine",
        probed_vector_size=384,
    )

    assert result is None
