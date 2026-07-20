from __future__ import annotations

import json
import sys
import types
from typing import Any

import httpx
import pytest

from private_rag.vector.embeddings import (
    LocalEmbeddingProviderFactory,
    OllamaEmbeddingError,
    OllamaEmbeddingProvider,
    SentenceTransformersEmbeddingProvider,
)


def test_sentence_transformers_provider_rejects_non_finite_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: Any) -> None:
            self.model_name = model_name
            self.kwargs = kwargs

        def get_sentence_embedding_dimension(self) -> int:
            return 2

        def encode(self, texts: list[str], *, normalize_embeddings: bool) -> list[list[float]]:
            return [[float("nan"), 1.0] for _ in texts]

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    provider = SentenceTransformersEmbeddingProvider("test-model")

    with pytest.raises(RuntimeError, match="non-finite vector values"):
        provider.embed(["query"])


def test_sentence_transformers_provider_passes_configured_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: Any) -> None:
            captured["model_name"] = model_name
            captured["kwargs"] = kwargs

        def get_sentence_embedding_dimension(self) -> int:
            return 2

        def encode(self, texts: list[str], *, normalize_embeddings: bool) -> list[list[float]]:
            return [[0.0, 1.0] for _ in texts]

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    provider = SentenceTransformersEmbeddingProvider("test-model", device="cpu")

    assert provider.embed(["query"]) == [[0.0, 1.0]]
    assert captured == {"model_name": "test-model", "kwargs": {"device": "cpu"}}


def test_sentence_transformers_provider_auto_device_falls_back_to_cpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    devices: list[str] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: Any) -> None:
            device = str(kwargs.get("device"))
            devices.append(device)
            if device == "mps":
                raise RuntimeError("accelerator unavailable")

        def get_sentence_embedding_dimension(self) -> int:
            return 2

        def encode(self, texts: list[str], *, normalize_embeddings: bool) -> list[list[float]]:
            return [[0.0, 1.0] for _ in texts]

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    fake_torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False),
        backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: True)),
    )
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    provider = SentenceTransformersEmbeddingProvider("test-model")

    assert provider.embed(["query"]) == [[0.0, 1.0]]
    assert devices == ["mps", "cpu"]


def test_local_embedding_provider_factory_uses_configured_sentence_transformers_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: Any) -> None:
            captured["model_name"] = model_name
            captured["kwargs"] = kwargs

        def get_sentence_embedding_dimension(self) -> int:
            return 768

        def encode(self, texts: list[str], *, normalize_embeddings: bool) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    factory = LocalEmbeddingProviderFactory(sentence_transformers_device="cpu")

    provider = factory.create(
        provider="sentence_transformers",
        model="sentence-transformers/all-mpnet-base-v2",
    )

    assert provider.model_name == "sentence-transformers/all-mpnet-base-v2"
    assert provider.vector_size == 768
    assert captured == {
        "model_name": "sentence-transformers/all-mpnet-base-v2",
        "kwargs": {"device": "cpu"},
    }


def test_local_embedding_provider_factory_creates_ollama_provider() -> None:
    factory = LocalEmbeddingProviderFactory(ollama_base_url="http://ollama.test")

    provider = factory.create(provider="ollama", model="embeddinggemma:300m")

    assert provider.model_name == "embeddinggemma:300m"
    assert provider.vector_size == 768


def test_ollama_embedding_provider_posts_batched_input_and_validates_vectors() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "embeddinggemma:300m",
                "embeddings": [[0.0, 1.0, 2.0], [3, 4, 5]],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(
        "http://ollama.test",
        "custom-embed:latest",
        client=client,
    )

    vectors = provider.embed(["alpha", "beta"])

    assert captured == {
        "url": "http://ollama.test/api/embed",
        "payload": {"model": "custom-embed:latest", "input": ["alpha", "beta"]},
    }
    assert vectors == [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]]
    assert provider.vector_size == 3


def test_ollama_embedding_provider_falls_back_to_legacy_embeddings_endpoint() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append({"url": str(request.url), "payload": payload})
        if str(request.url) == "http://ollama.test/api/embed":
            return httpx.Response(404, json={"error": "not found"}, request=request)
        legacy_vectors = {
            "alpha": [0.0, 1.0, 2.0],
            "beta": [3.0, 4.0, 5.0],
        }
        return httpx.Response(200, json={"embedding": legacy_vectors[payload["prompt"]]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(
        "http://ollama.test",
        "custom-embed:latest",
        client=client,
    )

    vectors = provider.embed(["alpha", "beta"])

    assert calls == [
        {
            "url": "http://ollama.test/api/embed",
            "payload": {"model": "custom-embed:latest", "input": ["alpha", "beta"]},
        },
        {
            "url": "http://ollama.test/api/embeddings",
            "payload": {"model": "custom-embed:latest", "prompt": "alpha"},
        },
        {
            "url": "http://ollama.test/api/embeddings",
            "payload": {"model": "custom-embed:latest", "prompt": "beta"},
        },
    ]
    assert vectors == [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]]


def test_ollama_embedding_provider_reports_known_registry_vector_size_without_probe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("known registry vector size should not require an HTTP probe")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(
        "http://ollama.test",
        "embeddinggemma:300m",
        client=client,
    )

    assert provider.vector_size == 768


def test_ollama_embedding_provider_probes_custom_model_vector_size() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "custom-embed:latest",
                "embeddings": [[0.1, 0.2, 0.3, 0.4]],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(
        "http://ollama.test",
        "custom-embed:latest",
        client=client,
    )

    assert provider.vector_size == 4


def test_ollama_embedding_provider_reports_missing_runtime_or_model_guidance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(
        "http://ollama.test",
        "embeddinggemma:300m",
        client=client,
    )

    with pytest.raises(OllamaEmbeddingError, match="ollama pull embeddinggemma:300m") as exc_info:
        provider.embed(["alpha"])
    assert exc_info.value.readiness_status == "not_installed"


def test_ollama_embedding_provider_reports_connection_guidance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(
        "http://ollama.test",
        "qwen3-embedding:8b",
        client=client,
    )

    with pytest.raises(OllamaEmbeddingError, match="Start Ollama") as exc_info:
        provider.embed(["alpha"])
    assert exc_info.value.readiness_status == "unavailable_runtime"


def test_ollama_embedding_provider_rejects_malformed_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "embeddinggemma:300m"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(
        "http://ollama.test",
        "embeddinggemma:300m",
        client=client,
    )

    with pytest.raises(RuntimeError, match="unexpected embedding response"):
        provider.embed(["alpha"])


def test_ollama_embedding_provider_rejects_non_finite_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'{"model":"embeddinggemma:300m","embeddings":[[NaN,1.0]]}',
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(
        "http://ollama.test",
        "embeddinggemma:300m",
        client=client,
    )

    with pytest.raises(RuntimeError, match="non-finite vector values"):
        provider.embed(["alpha"])


def test_ollama_embedding_provider_rejects_dimension_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"model": "embeddinggemma:300m", "embeddings": [[0.0, 1.0], [0.0]]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(
        "http://ollama.test",
        "embeddinggemma:300m",
        client=client,
    )

    with pytest.raises(RuntimeError, match="inconsistent vector dimensions"):
        provider.embed(["alpha", "beta"])
