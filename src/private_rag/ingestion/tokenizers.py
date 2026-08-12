from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from private_rag.repositories.schemas import RepositorySettings
from private_rag.vector.model_registry import lookup_embedding_model

TokenizerProvider = Literal["sentence_transformers", "ollama", "private_rag"]
TokenizerPrecision = Literal["exact", "fallback"]


@dataclass(frozen=True)
class TokenSpan:
    token: str
    char_start: int
    char_end: int


class TextTokenizer(Protocol):
    def encode(self, text: str) -> list[str]:
        """Return deterministic token strings for counting and future token windows."""

    def spans(self, text: str) -> list[TokenSpan]:
        """Return token spans in source text for char-range reconstruction."""

    def count(self, text: str) -> int:
        """Return token count for text."""


@dataclass(frozen=True)
class TokenizerMetadata:
    provider: TokenizerProvider
    tokenizer_name: str
    tokenizer_source: str
    precision: TokenizerPrecision
    fallback_reason: str | None = None

    def model_dump(self) -> dict[str, str]:
        payload = {
            "provider": self.provider,
            "tokenizer_name": self.tokenizer_name,
            "tokenizer_source": self.tokenizer_source,
            "precision": self.precision,
        }
        if self.fallback_reason:
            payload["fallback_reason"] = self.fallback_reason
        return payload


@dataclass(frozen=True)
class ResolvedTokenizer:
    tokenizer: TextTokenizer
    metadata: TokenizerMetadata


SentenceTransformersTokenizerLoader = Callable[[str], TextTokenizer]


FALLBACK_TOKENIZER_NAME = "private-rag/simple-token-fallback-v1"
_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class SimpleTokenFallbackTokenizer:
    def encode(self, text: str) -> list[str]:
        return [match.group(0) for match in _TOKEN_PATTERN.finditer(text)]

    def spans(self, text: str) -> list[TokenSpan]:
        return [
            TokenSpan(token=match.group(0), char_start=match.start(), char_end=match.end())
            for match in _TOKEN_PATTERN.finditer(text)
        ]

    def count(self, text: str) -> int:
        return len(self.encode(text))


class HuggingFaceTokenizer:
    def __init__(self, tokenizer: Any) -> None:
        self._tokenizer = tokenizer

    def encode(self, text: str) -> list[str]:
        tokens = self._tokenizer.encode(text, add_special_tokens=False)
        return [str(token) for token in tokens]

    def spans(self, text: str) -> list[TokenSpan]:
        try:
            encoded = self._tokenizer(
                text,
                add_special_tokens=False,
                return_offsets_mapping=True,
            )
        except Exception:
            return SimpleTokenFallbackTokenizer().spans(text)
        offsets = encoded.get("offset_mapping", [])
        input_ids = encoded.get("input_ids", [])
        return [
            TokenSpan(
                token=str(token_id),
                char_start=int(start),
                char_end=int(end),
            )
            for token_id, (start, end) in zip(input_ids, offsets, strict=False)
            if int(end) > int(start)
        ]

    def count(self, text: str) -> int:
        return len(self.encode(text))


def resolve_tokenizer(
    repository_settings: RepositorySettings,
    *,
    sentence_transformers_loader: SentenceTransformersTokenizerLoader | None = None,
) -> ResolvedTokenizer:
    provider = repository_settings.embedding.provider
    model = repository_settings.embedding.model
    if provider == "sentence_transformers":
        return _resolve_sentence_transformers_tokenizer(
            model,
            sentence_transformers_loader=sentence_transformers_loader,
        )
    if provider == "ollama":
        return _resolve_ollama_tokenizer(model)
    return _fallback(f"Unsupported embedding provider '{provider}'.")


def _resolve_sentence_transformers_tokenizer(
    model: str,
    *,
    sentence_transformers_loader: SentenceTransformersTokenizerLoader | None,
) -> ResolvedTokenizer:
    loader = sentence_transformers_loader or _load_huggingface_tokenizer
    try:
        tokenizer = loader(model)
    except Exception as exc:
        return _fallback(
            f"SentenceTransformers tokenizer for '{model}' is not available locally "
            f"({type(exc).__name__})."
        )
    return ResolvedTokenizer(
        tokenizer=tokenizer,
        metadata=TokenizerMetadata(
            provider="sentence_transformers",
            tokenizer_name=model,
            tokenizer_source="sentence_transformers_model",
            precision="exact",
        ),
    )


def _load_huggingface_tokenizer(model: str) -> TextTokenizer:
    from transformers import AutoTokenizer

    return HuggingFaceTokenizer(AutoTokenizer.from_pretrained(model, local_files_only=True))


def _resolve_ollama_tokenizer(model: str) -> ResolvedTokenizer:
    metadata = lookup_embedding_model("ollama", model)
    if metadata is not None and metadata.tokenizer_name and metadata.tokenizer_source:
        return ResolvedTokenizer(
            tokenizer=SimpleTokenFallbackTokenizer(),
            metadata=TokenizerMetadata(
                provider="ollama",
                tokenizer_name=metadata.tokenizer_name,
                tokenizer_source=metadata.tokenizer_source,
                precision=metadata.tokenizer_precision,
                fallback_reason=(
                    f"Ollama model '{model}' uses the registry-declared fallback tokenizer."
                    if metadata.tokenizer_precision == "fallback"
                    else None
                ),
            ),
        )
    return _fallback(f"Ollama model '{model}' does not have tokenizer registry metadata.")


def _fallback(reason: str) -> ResolvedTokenizer:
    return ResolvedTokenizer(
        tokenizer=SimpleTokenFallbackTokenizer(),
        metadata=TokenizerMetadata(
            provider="private_rag",
            tokenizer_name=FALLBACK_TOKENIZER_NAME,
            tokenizer_source="app_fallback",
            precision="fallback",
            fallback_reason=reason,
        ),
    )
