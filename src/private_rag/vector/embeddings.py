from __future__ import annotations

import hashlib
import math
from typing import Any, Protocol, cast

import httpx

from private_rag.vector.model_registry import lookup_embedding_model


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def vector_size(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingProviderFactory(Protocol):
    def create(self, *, provider: str, model: str) -> EmbeddingProvider: ...


EmbeddingProviderSource = EmbeddingProvider | EmbeddingProviderFactory


class LocalEmbeddingProviderFactory:
    def __init__(
        self,
        *,
        sentence_transformers_device: str | None = None,
        ollama_base_url: str = "http://localhost:11434",
    ) -> None:
        self._sentence_transformers_device = sentence_transformers_device
        self._ollama_base_url = ollama_base_url

    def create(self, *, provider: str, model: str) -> EmbeddingProvider:
        if provider == "sentence_transformers":
            return SentenceTransformersEmbeddingProvider(
                model,
                device=self._sentence_transformers_device,
            )
        if provider == "ollama":
            return OllamaEmbeddingProvider(self._ollama_base_url, model)
        raise ValueError(f"Unsupported embedding provider: {provider}.")


def resolve_embedding_provider(
    source: EmbeddingProviderSource,
    *,
    provider: str,
    model: str,
) -> EmbeddingProvider:
    create = getattr(source, "create", None)
    if callable(create):
        factory = cast(EmbeddingProviderFactory, source)
        return factory.create(provider=provider, model=model)

    embedder = cast(EmbeddingProvider, source)
    if embedder.model_name != model:
        raise RuntimeError(
            "Embedding provider does not match the requested model: "
            f"{embedder.model_name} != {model}."
        )
    return embedder


class SentenceTransformersEmbeddingProvider:
    def __init__(self, model_name: str, *, device: str | None = None) -> None:
        self._model_name = model_name
        self._device = device
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
        vectors = [list(map(float, vector)) for vector in encoded]
        if any(not math.isfinite(value) for vector in vectors for value in vector):
            raise RuntimeError(
                f"Embedding model returned non-finite vector values: {self._model_name}"
            )
        return vectors

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

        model_kwargs = {"device": self._device} if self._device is not None else {}
        model = SentenceTransformer(self._model_name, **model_kwargs)
        dimension = model.get_sentence_embedding_dimension()
        if dimension is None:
            raise RuntimeError(f"Embedding model has no known vector size: {self._model_name}")
        self._model = model
        self._vector_size = int(dimension)
        return model


class OllamaEmbeddingProvider:
    def __init__(
        self,
        base_url: str,
        model_name: str,
        *,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._timeout = timeout
        self._client = client
        metadata = lookup_embedding_model("ollama", model_name)
        self._vector_size = metadata.vector_size if metadata is not None else None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def vector_size(self) -> int:
        if self._vector_size is None:
            self._vector_size = len(self.embed(["dimension probe"])[0])
        return self._vector_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = self._post_embed(texts)
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise RuntimeError("Ollama returned an unexpected embedding response.")
        if len(embeddings) != len(texts):
            raise RuntimeError(
                "Ollama returned an unexpected number of embeddings: "
                f"{len(embeddings)} != {len(texts)}."
            )

        vectors = [self._coerce_vector(vector) for vector in embeddings]
        vector_sizes = {len(vector) for vector in vectors}
        if len(vector_sizes) != 1:
            raise RuntimeError(
                f"Ollama embedding model returned inconsistent vector dimensions: {vector_sizes}."
            )
        vector_size = vector_sizes.pop()
        if vector_size == 0:
            raise RuntimeError(
                f"Ollama embedding model returned empty vectors: {self._model_name}."
            )
        if self._vector_size is None:
            self._vector_size = vector_size
        elif vector_size != self._vector_size:
            raise RuntimeError(
                "Ollama embedding model vector size changed between calls: "
                f"{vector_size} != {self._vector_size}."
            )
        return vectors

    def _post_embed(self, texts: list[str]) -> dict[str, object]:
        client = self._client or httpx.Client(timeout=self._timeout)
        close_client = self._client is None
        try:
            response = client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model_name, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Ollama is not reachable or embedding model '{self._model_name}' is unavailable. "
                f"Start Ollama and run `ollama pull {self._model_name}`."
            ) from exc
        except ValueError as exc:
            raise RuntimeError("Ollama returned an unexpected response body.") from exc
        finally:
            if close_client:
                client.close()
        if not isinstance(payload, dict):
            raise RuntimeError("Ollama returned an unexpected response body.")
        return payload

    def _coerce_vector(self, raw_vector: object) -> list[float]:
        if not isinstance(raw_vector, list):
            raise RuntimeError("Ollama returned an unexpected embedding vector.")
        vector: list[float] = []
        for value in raw_vector:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise RuntimeError(
                    f"Ollama embedding model returned non-numeric vector values: {self._model_name}."
                )
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise RuntimeError(
                    f"Ollama embedding model returned non-finite vector values: {self._model_name}."
                )
            vector.append(numeric_value)
        return vector


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
