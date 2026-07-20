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
        sentence_transformers_device: str | None = "auto",
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
    def __init__(self, model_name: str, *, device: str | None = "auto") -> None:
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

        model = self._load_sentence_transformer(SentenceTransformer)
        dimension = model.get_sentence_embedding_dimension()
        if dimension is None:
            raise RuntimeError(f"Embedding model has no known vector size: {self._model_name}")
        self._model = model
        self._vector_size = int(dimension)
        return model

    def _load_sentence_transformer(self, sentence_transformer: Any) -> Any:
        if self._device and self._device != "auto":
            return sentence_transformer(self._model_name, device=self._device)

        preferred_device = _preferred_sentence_transformers_device()
        try:
            return sentence_transformer(self._model_name, device=preferred_device)
        except Exception:
            if preferred_device == "cpu":
                raise
            return sentence_transformer(self._model_name, device="cpu")


def _preferred_sentence_transformers_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"

    cuda = getattr(torch, "cuda", None)
    if cuda is not None and callable(getattr(cuda, "is_available", None)):
        try:
            if cuda.is_available():
                return "cuda"
        except Exception:
            pass

    backends = getattr(torch, "backends", None)
    mps = getattr(backends, "mps", None) if backends is not None else None
    if mps is not None and callable(getattr(mps, "is_available", None)):
        try:
            if mps.is_available():
                return "mps"
        except Exception:
            pass
    return "cpu"


class OllamaEmbeddingError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        readiness_status: str = "failed",
        allow_legacy_fallback: bool = False,
    ) -> None:
        super().__init__(message)
        self.readiness_status = readiness_status
        self.allow_legacy_fallback = allow_legacy_fallback


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
            try:
                return self._post_current_embed(client, texts)
            except OllamaEmbeddingError as exc:
                if not exc.allow_legacy_fallback:
                    raise
            payload = self._post_legacy_embeddings(client, texts)
        finally:
            if close_client:
                client.close()
        if not isinstance(payload, dict):
            raise RuntimeError("Ollama returned an unexpected response body.")
        return payload

    def _post_current_embed(
        self,
        client: httpx.Client,
        texts: list[str],
    ) -> dict[str, object]:
        try:
            response = client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model_name, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {400, 404, 405}:
                raise OllamaEmbeddingError(
                    f"Ollama /api/embed is not compatible with model '{self._model_name}' "
                    "from this runtime.",
                    readiness_status="failed",
                    allow_legacy_fallback=True,
                ) from exc
            raise OllamaEmbeddingError(
                f"Ollama embedding request failed for model '{self._model_name}'. "
                "Check the local Ollama logs and rerun readiness.",
                readiness_status="failed",
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaEmbeddingError(
                f"Ollama is not reachable at {self._base_url}. Start Ollama, then run "
                f"`ollama pull {self._model_name}` if needed.",
                readiness_status="unavailable_runtime",
            ) from exc
        except ValueError as exc:
            raise RuntimeError("Ollama returned an unexpected response body.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Ollama returned an unexpected response body.")
        return payload

    def _post_legacy_embeddings(
        self,
        client: httpx.Client,
        texts: list[str],
    ) -> dict[str, object]:
        embeddings: list[object] = []
        for text in texts:
            payload = self._post_legacy_embedding(client, text)
            embeddings.append(payload.get("embedding"))
        return {"model": self._model_name, "embeddings": embeddings}

    def _post_legacy_embedding(
        self,
        client: httpx.Client,
        text: str,
    ) -> dict[str, object]:
        try:
            response = client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model_name, "prompt": text},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise OllamaEmbeddingError(
                    f"Ollama embedding model '{self._model_name}' is not installed. "
                    f"Run `ollama pull {self._model_name}`.",
                    readiness_status="not_installed",
                ) from exc
            raise OllamaEmbeddingError(
                f"Ollama embedding request failed for model '{self._model_name}'. "
                "Check the local Ollama logs and rerun readiness.",
                readiness_status="failed",
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaEmbeddingError(
                f"Ollama is not reachable at {self._base_url}. Start Ollama, then run "
                f"`ollama pull {self._model_name}` if needed.",
                readiness_status="unavailable_runtime",
            ) from exc
        except ValueError as exc:
            raise RuntimeError("Ollama returned an unexpected response body.") from exc
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
