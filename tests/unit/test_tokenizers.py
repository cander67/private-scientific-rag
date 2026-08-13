from __future__ import annotations

import json

import httpx
import pytest

from private_rag.core.settings import Settings
from private_rag.ingestion.tokenizers import (
    SimpleTokenFallbackTokenizer,
    TokenSpan,
    resolve_tokenizer,
)
from private_rag.repositories.schemas import RepositorySettings


class FakeTokenizer:
    def encode(self, text: str) -> list[str]:
        return text.split()

    def spans(self, text: str) -> list[TokenSpan]:
        return []

    def count(self, text: str) -> int:
        return len(self.encode(text))


def test_sentence_transformers_resolution_uses_model_tokenizer_loader() -> None:
    settings = RepositorySettings.from_app_settings(Settings())

    resolved = resolve_tokenizer(
        settings,
        sentence_transformers_loader=lambda model: FakeTokenizer(),
    )

    assert resolved.metadata.model_dump() == {
        "provider": "sentence_transformers",
        "tokenizer_id": "hf:sentence-transformers/all-MiniLM-L6-v2",
        "tokenizer_name": "sentence-transformers/all-MiniLM-L6-v2",
        "tokenizer_source": "sentence_transformers_model",
        "implementation_library": "transformers",
        "precision": "exact",
        "selection_mode": "auto",
        "offset_mapping": True,
        "is_fallback": False,
    }
    assert resolved.tokenizer.count("alpha beta gamma") == 3


def test_sentence_transformers_resolution_records_fallback_when_loader_fails() -> None:
    settings = RepositorySettings.from_app_settings(Settings())

    def fail(_model: str) -> FakeTokenizer:
        raise OSError("not cached")

    resolved = resolve_tokenizer(settings, sentence_transformers_loader=fail)

    metadata = resolved.metadata.model_dump()
    assert metadata["provider"] == "private_rag"
    assert metadata["tokenizer_id"] == "private-rag/simple-token-fallback-v1"
    assert metadata["implementation_library"] == "regex"
    assert metadata["tokenizer_source"] == "app_fallback"
    assert metadata["precision"] == "fallback"
    assert metadata["selection_mode"] == "auto"
    assert metadata["is_fallback"] is True
    fallback_reason = metadata["fallback_reason"]
    assert isinstance(fallback_reason, str)
    assert "SentenceTransformers tokenizer" in fallback_reason


def test_known_ollama_resolution_uses_registry_declared_strategy() -> None:
    payload = RepositorySettings.from_app_settings(Settings()).model_dump(mode="json")
    payload["embedding"]["provider"] = "ollama"
    payload["embedding"]["model"] = "embeddinggemma:300m"
    payload["vector"]["vector_size"] = 768
    settings = RepositorySettings.model_validate(payload)

    resolved = resolve_tokenizer(settings)

    assert resolved.metadata.model_dump() == {
        "provider": "ollama",
        "tokenizer_id": "private-rag/simple-token-fallback-v1",
        "tokenizer_name": "private-rag/simple-token-fallback-v1",
        "tokenizer_source": "ollama_registry_fallback",
        "implementation_library": "regex",
        "precision": "fallback",
        "selection_mode": "auto",
        "offset_mapping": True,
        "is_fallback": True,
        "fallback_reason": (
            "Ollama model 'embeddinggemma:300m' uses the registry-declared fallback tokenizer."
        ),
    }


def test_ollama_resolution_prefers_runtime_tokenizer_when_available() -> None:
    payload = RepositorySettings.from_app_settings(Settings()).model_dump(mode="json")
    payload["embedding"]["provider"] = "ollama"
    payload["embedding"]["model"] = "embeddinggemma:300m"
    payload["vector"]["vector_size"] = 768
    settings = RepositorySettings.model_validate(payload)
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"tokens": [101, 202, 303]})

    resolved = resolve_tokenizer(
        settings,
        ollama_base_url="http://ollama.test",
        ollama_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert resolved.metadata.model_dump() == {
        "provider": "ollama",
        "tokenizer_id": "ollama:embeddinggemma:300m",
        "tokenizer_name": "embeddinggemma:300m",
        "tokenizer_source": "ollama_runtime",
        "implementation_library": "ollama",
        "precision": "exact",
        "selection_mode": "auto",
        "offset_mapping": False,
        "is_fallback": False,
    }
    assert resolved.tokenizer.count("LiFePO4 + C-rate") == 3
    assert requests == [
        {"model": "embeddinggemma:300m", "prompt": "tokenizer readiness probe"},
        {"model": "embeddinggemma:300m", "prompt": "LiFePO4 + C-rate"},
    ]


def test_ollama_resolution_falls_back_when_runtime_endpoint_is_unsupported() -> None:
    payload = RepositorySettings.from_app_settings(Settings()).model_dump(mode="json")
    payload["embedding"]["provider"] = "ollama"
    payload["embedding"]["model"] = "embeddinggemma:300m"
    payload["vector"]["vector_size"] = 768
    settings = RepositorySettings.model_validate(payload)

    resolved = resolve_tokenizer(
        settings,
        ollama_base_url="http://ollama.test",
        ollama_client=httpx.Client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(404))
        ),
    )

    metadata = resolved.metadata.model_dump()
    assert metadata["implementation_library"] == "regex"
    assert metadata["precision"] == "fallback"
    fallback_reason = metadata["fallback_reason"]
    assert isinstance(fallback_reason, str)
    assert "Ollama runtime tokenizer" in fallback_reason
    assert "registry-declared fallback tokenizer" in fallback_reason


def test_ollama_resolution_falls_back_when_runtime_response_is_malformed() -> None:
    payload = RepositorySettings.from_app_settings(Settings()).model_dump(mode="json")
    payload["embedding"]["provider"] = "ollama"
    payload["embedding"]["model"] = "custom-local:latest"
    payload["vector"]["vector_size"] = 768
    settings = RepositorySettings.model_validate(payload)

    resolved = resolve_tokenizer(
        settings,
        ollama_base_url="http://ollama.test",
        ollama_client=httpx.Client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
        ),
    )

    metadata = resolved.metadata.model_dump()
    assert metadata["provider"] == "private_rag"
    assert metadata["implementation_library"] == "regex"
    fallback_reason = metadata["fallback_reason"]
    assert isinstance(fallback_reason, str)
    assert "Ollama runtime tokenizer" in fallback_reason
    assert "does not have tokenizer registry metadata" in fallback_reason


def test_custom_ollama_resolution_uses_app_fallback() -> None:
    payload = RepositorySettings.from_app_settings(Settings()).model_dump(mode="json")
    payload["embedding"]["provider"] = "ollama"
    payload["embedding"]["model"] = "custom-local:latest"
    payload["vector"]["vector_size"] = 768
    settings = RepositorySettings.model_validate(payload)

    resolved = resolve_tokenizer(settings)

    metadata = resolved.metadata.model_dump()
    assert metadata["provider"] == "private_rag"
    assert metadata["tokenizer_source"] == "app_fallback"
    assert metadata["implementation_library"] == "regex"
    assert metadata["precision"] == "fallback"
    fallback_reason = metadata["fallback_reason"]
    assert isinstance(fallback_reason, str)
    assert "does not have tokenizer registry metadata" in fallback_reason


def test_manual_tiktoken_tokenizer_is_not_supported() -> None:
    payload = RepositorySettings.from_app_settings(Settings()).model_dump(mode="json")
    payload["chunking"]["tokenizer_mode"] = "manual"
    payload["chunking"]["tokenizer_id"] = "tiktoken:cl100k_base"

    with pytest.raises(ValueError, match="Unsupported chunk tokenizer"):
        RepositorySettings.model_validate(payload)


def test_manual_sentence_transformers_resolution_uses_catalog_entry() -> None:
    payload = RepositorySettings.from_app_settings(Settings()).model_dump(mode="json")
    payload["chunking"]["tokenizer_mode"] = "manual"
    payload["chunking"]["tokenizer_id"] = "hf:sentence-transformers/all-mpnet-base-v2"
    settings = RepositorySettings.model_validate(payload)

    resolved = resolve_tokenizer(
        settings,
        sentence_transformers_loader=lambda _model: FakeTokenizer(),
    )

    metadata = resolved.metadata.model_dump()
    assert metadata["tokenizer_id"] == "hf:sentence-transformers/all-mpnet-base-v2"
    assert metadata["tokenizer_name"] == "sentence-transformers/all-mpnet-base-v2"
    assert metadata["implementation_library"] == "transformers"
    assert metadata["selection_mode"] == "manual"
    assert metadata["precision"] == "exact"


def test_manual_unavailable_exact_tokenizer_falls_back_with_reason() -> None:
    payload = RepositorySettings.from_app_settings(Settings()).model_dump(mode="json")
    payload["chunking"]["tokenizer_mode"] = "manual"
    payload["chunking"]["tokenizer_id"] = "hf:sentence-transformers/all-mpnet-base-v2"
    settings = RepositorySettings.model_validate(payload)

    def fail(_model: str) -> FakeTokenizer:
        raise OSError("not cached")

    resolved = resolve_tokenizer(settings, sentence_transformers_loader=fail)

    metadata = resolved.metadata.model_dump()
    assert metadata["tokenizer_id"] == "private-rag/simple-token-fallback-v1"
    assert metadata["implementation_library"] == "regex"
    assert metadata["selection_mode"] == "manual"
    fallback_reason = metadata["fallback_reason"]
    assert isinstance(fallback_reason, str)
    assert "Manual HuggingFace tokenizer" in fallback_reason


def test_simple_fallback_tokenizer_counts_words_symbols_and_formula_tokens() -> None:
    tokenizer = SimpleTokenFallbackTokenizer()

    assert tokenizer.encode("LiFePO4 + C-rate") == ["LiFePO4", "+", "C", "-", "rate"]
    assert [(span.token, span.char_start, span.char_end) for span in tokenizer.spans("A + B")] == [
        ("A", 0, 1),
        ("+", 2, 3),
        ("B", 4, 5),
    ]
