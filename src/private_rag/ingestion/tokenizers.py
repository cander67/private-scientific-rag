from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from private_rag.ingestion.tokenizer_catalog import (
    FALLBACK_TOKENIZER_ID,
    TokenizerImplementationLibrary,
    TokenizerPrecision,
    TokenizerProvider,
    huggingface_tokenizer_id,
    lookup_tokenizer_catalog_entry,
)
from private_rag.repositories.schemas import RepositorySettings
from private_rag.vector.model_registry import lookup_embedding_model

TokenizerSelectionMode = Literal["auto", "manual"]


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
    tokenizer_id: str
    tokenizer_name: str
    tokenizer_source: str
    implementation_library: TokenizerImplementationLibrary
    precision: TokenizerPrecision
    selection_mode: TokenizerSelectionMode = "auto"
    offset_mapping: bool = True
    is_fallback: bool = False
    fallback_reason: str | None = None

    def model_dump(self) -> dict[str, object]:
        payload = {
            "provider": self.provider,
            "tokenizer_id": self.tokenizer_id,
            "tokenizer_name": self.tokenizer_name,
            "tokenizer_source": self.tokenizer_source,
            "implementation_library": self.implementation_library,
            "precision": self.precision,
            "selection_mode": self.selection_mode,
            "offset_mapping": self.offset_mapping,
            "is_fallback": self.is_fallback,
        }
        if self.fallback_reason:
            payload["fallback_reason"] = self.fallback_reason
        return payload


@dataclass(frozen=True)
class ResolvedTokenizer:
    tokenizer: TextTokenizer
    metadata: TokenizerMetadata


SentenceTransformersTokenizerLoader = Callable[[str], TextTokenizer]


FALLBACK_TOKENIZER_NAME = FALLBACK_TOKENIZER_ID
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


class TiktokenTokenizer:
    def __init__(self, encoding_name: str) -> None:
        import tiktoken

        self._encoding = tiktoken.get_encoding(encoding_name)

    def encode(self, text: str) -> list[str]:
        return [str(token) for token in self._encoding.encode(text)]

    def spans(self, text: str) -> list[TokenSpan]:
        token_ids = self._encoding.encode(text)
        decoded, offsets = self._encoding.decode_with_offsets(token_ids)
        if decoded != text:
            return SimpleTokenFallbackTokenizer().spans(text)
        return [
            TokenSpan(
                token=str(token_id),
                char_start=int(offset),
                char_end=int(offsets[index + 1] if index + 1 < len(offsets) else len(text)),
            )
            for index, (token_id, offset) in enumerate(zip(token_ids, offsets, strict=False))
        ]

    def count(self, text: str) -> int:
        return len(self.encode(text))


def resolve_tokenizer(
    repository_settings: RepositorySettings,
    *,
    sentence_transformers_loader: SentenceTransformersTokenizerLoader | None = None,
) -> ResolvedTokenizer:
    if repository_settings.chunking.tokenizer_mode == "manual":
        return _resolve_manual_tokenizer(
            repository_settings.chunking.tokenizer_id,
            sentence_transformers_loader=sentence_transformers_loader,
        )
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
            tokenizer_id=huggingface_tokenizer_id(model),
            tokenizer_name=model,
            tokenizer_source="sentence_transformers_model",
            implementation_library="transformers",
            precision="exact",
            selection_mode="auto",
            offset_mapping=True,
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
                tokenizer_id=metadata.tokenizer_id or FALLBACK_TOKENIZER_NAME,
                tokenizer_name=metadata.tokenizer_name,
                tokenizer_source=metadata.tokenizer_source,
                implementation_library=cast(
                    TokenizerImplementationLibrary,
                    metadata.tokenizer_implementation_library or "regex",
                ),
                precision=metadata.tokenizer_precision,
                selection_mode="auto",
                offset_mapping=metadata.tokenizer_offset_mapping,
                is_fallback=metadata.tokenizer_precision == "fallback",
                fallback_reason=(
                    f"Ollama model '{model}' uses the registry-declared fallback tokenizer."
                    if metadata.tokenizer_precision == "fallback"
                    else None
                ),
            ),
        )
    return _fallback(f"Ollama model '{model}' does not have tokenizer registry metadata.")


def _resolve_manual_tokenizer(
    tokenizer_id: str | None,
    *,
    sentence_transformers_loader: SentenceTransformersTokenizerLoader | None,
) -> ResolvedTokenizer:
    if tokenizer_id is None:
        return _fallback(
            "Manual tokenizer selection requires tokenizer_id.", selection_mode="manual"
        )
    entry = lookup_tokenizer_catalog_entry(tokenizer_id)
    if entry is None:
        return _fallback(
            f"Manual tokenizer '{tokenizer_id}' is not in the tokenizer catalog.",
            selection_mode="manual",
        )
    if entry.implementation_library == "regex":
        return _fallback("Manual fallback tokenizer selected.", selection_mode="manual")
    if entry.implementation_library == "tiktoken":
        return ResolvedTokenizer(
            tokenizer=TiktokenTokenizer(entry.tokenizer_name),
            metadata=TokenizerMetadata(
                provider=entry.provider,
                tokenizer_id=entry.id,
                tokenizer_name=entry.tokenizer_name,
                tokenizer_source=entry.tokenizer_source,
                implementation_library=entry.implementation_library,
                precision=entry.precision,
                selection_mode="manual",
                offset_mapping=entry.offset_mapping,
                is_fallback=entry.is_fallback,
            ),
        )
    loader = sentence_transformers_loader or _load_huggingface_tokenizer
    try:
        tokenizer = loader(entry.tokenizer_name)
    except Exception as exc:
        return _fallback(
            f"Manual HuggingFace tokenizer '{entry.tokenizer_name}' is not available locally "
            f"({type(exc).__name__}).",
            selection_mode="manual",
        )
    return ResolvedTokenizer(
        tokenizer=tokenizer,
        metadata=TokenizerMetadata(
            provider=entry.provider,
            tokenizer_id=entry.id,
            tokenizer_name=entry.tokenizer_name,
            tokenizer_source=entry.tokenizer_source,
            implementation_library=entry.implementation_library,
            precision=entry.precision,
            selection_mode="manual",
            offset_mapping=entry.offset_mapping,
            is_fallback=entry.is_fallback,
        ),
    )


def _fallback(reason: str, *, selection_mode: TokenizerSelectionMode = "auto") -> ResolvedTokenizer:
    return ResolvedTokenizer(
        tokenizer=SimpleTokenFallbackTokenizer(),
        metadata=TokenizerMetadata(
            provider="private_rag",
            tokenizer_id=FALLBACK_TOKENIZER_NAME,
            tokenizer_name=FALLBACK_TOKENIZER_NAME,
            tokenizer_source="app_fallback",
            implementation_library="regex",
            precision="fallback",
            selection_mode=selection_mode,
            offset_mapping=True,
            is_fallback=True,
            fallback_reason=reason,
        ),
    )
