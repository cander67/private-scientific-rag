from __future__ import annotations

import hashlib
import math
from typing import Any, Protocol


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def vector_size(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformersEmbeddingProvider:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: Any | None = None
        self._vector_size: int | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def vector_size(self) -> int:
        self._load_model()
        if self._vector_size is None:
            raise RuntimeError("Embedding model vector size is unavailable")
        return self._vector_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        encoded = model.encode(texts, normalize_embeddings=True)
        return [list(map(float, vector)) for vector in encoded]

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "SentenceTransformers is not installed. Install vector search dependencies "
                "before rebuilding the vector index."
            ) from exc

        model = SentenceTransformer(self._model_name)
        dimension = model.get_sentence_embedding_dimension()
        if dimension is None:
            raise RuntimeError(f"Embedding model has no known vector size: {self._model_name}")
        self._model = model
        self._vector_size = int(dimension)
        return model


class DeterministicEmbeddingProvider:
    def __init__(self, model_name: str = "test-deterministic", vector_size: int = 8) -> None:
        self._model_name = model_name
        self._vector_size = vector_size

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def vector_size(self) -> int:
        return self._vector_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        values = [0.0 for _ in range(self._vector_size)]
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            values[digest[0] % self._vector_size] += 1.0 + digest[1] / 255.0
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]
