from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EmbeddingProviderName = Literal["sentence_transformers", "ollama"]
VectorDistance = Literal["cosine", "dot", "euclid"]


@dataclass(frozen=True)
class EmbeddingModelMetadata:
    provider: EmbeddingProviderName
    model: str
    label: str
    vector_size: int
    supported_distances: tuple[VectorDistance, ...]
    resource_notes: str
    setup_hint: str
    requires_local_model: bool
    requires_live_probe: bool = False


class EmbeddingModelCompatibilityError(ValueError):
    pass


KNOWN_EMBEDDING_MODELS: tuple[EmbeddingModelMetadata, ...] = (
    EmbeddingModelMetadata(
        provider="sentence_transformers",
        model="sentence-transformers/all-MiniLM-L6-v2",
        label="MiniLM baseline",
        vector_size=384,
        supported_distances=("cosine", "dot", "euclid"),
        resource_notes="Small local SentenceTransformers baseline for fast CPU indexing.",
        setup_hint="Install/cache with SentenceTransformers before rebuilding.",
        requires_local_model=True,
    ),
    EmbeddingModelMetadata(
        provider="sentence_transformers",
        model="sentence-transformers/all-mpnet-base-v2",
        label="MPNet base",
        vector_size=768,
        supported_distances=("cosine", "dot", "euclid"),
        resource_notes="Higher-quality SentenceTransformers model with a larger vector size.",
        setup_hint="Install/cache with SentenceTransformers before rebuilding.",
        requires_local_model=True,
    ),
    EmbeddingModelMetadata(
        provider="ollama",
        model="embeddinggemma:300m",
        label="EmbeddingGemma 300M",
        vector_size=768,
        supported_distances=("cosine",),
        resource_notes="Lightweight multilingual Ollama embedding model with a 2K context window.",
        setup_hint="Start Ollama, then run `ollama pull embeddinggemma:300m`.",
        requires_local_model=True,
    ),
    EmbeddingModelMetadata(
        provider="ollama",
        model="qwen3-embedding:8b",
        label="Qwen3 Embedding 8B",
        vector_size=4096,
        supported_distances=("cosine",),
        resource_notes="Larger multilingual Ollama embedding model for high-capacity retrieval.",
        setup_hint="Start Ollama, then run `ollama pull qwen3-embedding:8b`.",
        requires_local_model=True,
    ),
)


def known_embedding_models() -> tuple[EmbeddingModelMetadata, ...]:
    return KNOWN_EMBEDDING_MODELS


def lookup_embedding_model(
    provider: str,
    model: str,
) -> EmbeddingModelMetadata | None:
    for metadata in KNOWN_EMBEDDING_MODELS:
        if metadata.provider == provider and metadata.model == model:
            return metadata
    return None


def lookup_embedding_model_by_name(model: str) -> EmbeddingModelMetadata | None:
    for metadata in KNOWN_EMBEDDING_MODELS:
        if metadata.model == model:
            return metadata
    return None


def is_custom_ollama_embedding_model(provider: str, model: str) -> bool:
    return provider == "ollama" and lookup_embedding_model(provider, model) is None


def validate_embedding_model_settings(
    *,
    provider: str,
    model: str,
    vector_size: int,
    distance: str,
    probed_vector_size: int | None = None,
) -> EmbeddingModelMetadata | None:
    metadata = lookup_embedding_model(provider, model)
    if metadata is None:
        known_name = lookup_embedding_model_by_name(model)
        if known_name is not None:
            raise EmbeddingModelCompatibilityError(
                f"Embedding model '{model}' belongs to provider '{known_name.provider}', "
                f"not '{provider}'."
            )
        if provider == "sentence_transformers":
            if probed_vector_size is not None and probed_vector_size != vector_size:
                raise EmbeddingModelCompatibilityError(
                    "SentenceTransformers embedding model vector size does not match "
                    f"repository settings: {probed_vector_size} != {vector_size}."
                )
            return None
        if provider != "ollama":
            raise EmbeddingModelCompatibilityError(f"Unsupported embedding provider: {provider}.")
        if distance != "cosine":
            raise EmbeddingModelCompatibilityError(
                "Custom Ollama embedding models currently require cosine distance."
            )
        if probed_vector_size is None:
            raise EmbeddingModelCompatibilityError(
                "Custom Ollama embedding models require a successful live dimension probe "
                "before rebuilding the vector index."
            )
        if probed_vector_size != vector_size:
            raise EmbeddingModelCompatibilityError(
                "Custom Ollama embedding model vector size does not match repository settings: "
                f"{probed_vector_size} != {vector_size}."
            )
        return None

    if provider != metadata.provider:
        raise EmbeddingModelCompatibilityError(
            f"Embedding model '{model}' belongs to provider '{metadata.provider}', not '{provider}'."
        )
    if distance not in metadata.supported_distances:
        supported = ", ".join(metadata.supported_distances)
        raise EmbeddingModelCompatibilityError(
            f"Embedding model '{model}' does not support distance '{distance}'. "
            f"Supported distances: {supported}."
        )
    if vector_size != metadata.vector_size:
        raise EmbeddingModelCompatibilityError(
            f"Embedding model '{model}' expects vector size {metadata.vector_size}, "
            f"but repository settings use {vector_size}."
        )
    return metadata
