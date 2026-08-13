from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

import httpx

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


class OllamaRuntimeTokenizer:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client
        self._cache: dict[str, list[str]] = {}

    def encode(self, text: str) -> list[str]:
        if text in self._cache:
            return self._cache[text]
        tokens = self._tokenize(text)
        self._cache[text] = tokens
        return tokens

    def spans(self, text: str) -> list[TokenSpan]:
        return SimpleTokenFallbackTokenizer().spans(text)

    def count(self, text: str) -> int:
        return len(self.encode(text))

    def _tokenize(self, text: str) -> list[str]:
        payload = {"model": self._model, "prompt": text}
        if self._client is not None:
            response = self._client.post(f"{self._base_url}/api/tokenize", json=payload)
            response.raise_for_status()
            return _tokens_from_ollama_response(response.json())
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{self._base_url}/api/tokenize", json=payload)
            response.raise_for_status()
            return _tokens_from_ollama_response(response.json())


def _tokens_from_ollama_response(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        raise ValueError("Ollama tokenizer response must be a JSON object.")
    raw_tokens = payload.get("tokens")
    if raw_tokens is None:
        raw_tokens = payload.get("token_ids")
    if not isinstance(raw_tokens, list):
        raise ValueError("Ollama tokenizer response did not include a token list.")
    return [str(token) for token in raw_tokens]


def resolve_tokenizer(
    repository_settings: RepositorySettings,
    *,
    sentence_transformers_loader: SentenceTransformersTokenizerLoader | None = None,
    ollama_base_url: str | None = None,
    ollama_client: httpx.Client | None = None,
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
        return _resolve_ollama_tokenizer(
            model,
            ollama_base_url=ollama_base_url,
            ollama_client=ollama_client,
            sentence_transformers_loader=sentence_transformers_loader,
        )
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


def _resolve_ollama_tokenizer(
    model: str,
    *,
    ollama_base_url: str | None,
    ollama_client: httpx.Client | None,
    sentence_transformers_loader: SentenceTransformersTokenizerLoader | None,
) -> ResolvedTokenizer:
    runtime_fallback_reason: str | None = None
    if ollama_base_url:
        try:
            runtime_tokenizer = OllamaRuntimeTokenizer(
                base_url=ollama_base_url,
                model=model,
                client=ollama_client,
            )
            runtime_tokenizer.count("tokenizer readiness probe")
        except Exception as exc:
            runtime_fallback_reason = (
                f"Ollama runtime tokenizer for '{model}' is unavailable ({type(exc).__name__})."
            )
        else:
            return ResolvedTokenizer(
                tokenizer=runtime_tokenizer,
                metadata=TokenizerMetadata(
                    provider="ollama",
                    tokenizer_id=f"ollama:{model}",
                    tokenizer_name=model,
                    tokenizer_source="ollama_runtime",
                    implementation_library="ollama",
                    precision="exact",
                    selection_mode="auto",
                    offset_mapping=False,
                ),
            )

    metadata = lookup_embedding_model("ollama", model)
    if metadata is not None and metadata.tokenizer_name and metadata.tokenizer_source:
        if metadata.tokenizer_implementation_library == "transformers":
            loader = sentence_transformers_loader or _load_huggingface_tokenizer
            try:
                registry_tokenizer = loader(metadata.tokenizer_name)
            except Exception as exc:
                return _fallback(
                    _append_runtime_fallback_reason(
                        f"Ollama registry HuggingFace tokenizer '{metadata.tokenizer_name}' "
                        f"is not available locally ({type(exc).__name__}).",
                        runtime_fallback_reason,
                    )
                )
            return ResolvedTokenizer(
                tokenizer=registry_tokenizer,
                metadata=TokenizerMetadata(
                    provider="ollama",
                    tokenizer_id=metadata.tokenizer_id
                    or huggingface_tokenizer_id(metadata.tokenizer_name),
                    tokenizer_name=metadata.tokenizer_name,
                    tokenizer_source=metadata.tokenizer_source,
                    implementation_library="transformers",
                    precision=metadata.tokenizer_precision,
                    selection_mode="auto",
                    offset_mapping=metadata.tokenizer_offset_mapping,
                    is_fallback=metadata.tokenizer_precision == "fallback",
                    fallback_reason=(
                        _append_runtime_fallback_reason(
                            f"Ollama model '{model}' uses fallback registry metadata.",
                            runtime_fallback_reason,
                        )
                        if metadata.tokenizer_precision == "fallback"
                        else runtime_fallback_reason
                    ),
                ),
            )
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
                    _append_runtime_fallback_reason(
                        f"Ollama model '{model}' uses the registry-declared fallback tokenizer.",
                        runtime_fallback_reason,
                    )
                    if metadata.tokenizer_precision == "fallback"
                    else None
                ),
            ),
        )
    return _fallback(
        _append_runtime_fallback_reason(
            f"Ollama model '{model}' does not have tokenizer registry metadata.",
            runtime_fallback_reason,
        )
    )


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


def _append_runtime_fallback_reason(reason: str, runtime_reason: str | None) -> str:
    if runtime_reason:
        return f"{runtime_reason} {reason}"
    return reason
