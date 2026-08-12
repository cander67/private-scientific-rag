from __future__ import annotations

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
        "tokenizer_name": "sentence-transformers/all-MiniLM-L6-v2",
        "tokenizer_source": "sentence_transformers_model",
        "precision": "exact",
    }
    assert resolved.tokenizer.count("alpha beta gamma") == 3


def test_sentence_transformers_resolution_records_fallback_when_loader_fails() -> None:
    settings = RepositorySettings.from_app_settings(Settings())

    def fail(_model: str) -> FakeTokenizer:
        raise OSError("not cached")

    resolved = resolve_tokenizer(settings, sentence_transformers_loader=fail)

    metadata = resolved.metadata.model_dump()
    assert metadata["provider"] == "private_rag"
    assert metadata["tokenizer_source"] == "app_fallback"
    assert metadata["precision"] == "fallback"
    assert "SentenceTransformers tokenizer" in metadata["fallback_reason"]


def test_known_ollama_resolution_uses_registry_declared_strategy() -> None:
    payload = RepositorySettings.from_app_settings(Settings()).model_dump(mode="json")
    payload["embedding"]["provider"] = "ollama"
    payload["embedding"]["model"] = "embeddinggemma:300m"
    payload["vector"]["vector_size"] = 768
    settings = RepositorySettings.model_validate(payload)

    resolved = resolve_tokenizer(settings)

    assert resolved.metadata.model_dump() == {
        "provider": "ollama",
        "tokenizer_name": "private-rag/simple-token-fallback-v1",
        "tokenizer_source": "ollama_registry_fallback",
        "precision": "fallback",
        "fallback_reason": (
            "Ollama model 'embeddinggemma:300m' uses the registry-declared fallback tokenizer."
        ),
    }


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
    assert metadata["precision"] == "fallback"
    assert "does not have tokenizer registry metadata" in metadata["fallback_reason"]


def test_simple_fallback_tokenizer_counts_words_symbols_and_formula_tokens() -> None:
    tokenizer = SimpleTokenFallbackTokenizer()

    assert tokenizer.encode("LiFePO4 + C-rate") == ["LiFePO4", "+", "C", "-", "rate"]
    assert [(span.token, span.char_start, span.char_end) for span in tokenizer.spans("A + B")] == [
        ("A", 0, 1),
        ("+", 2, 3),
        ("B", 4, 5),
    ]
