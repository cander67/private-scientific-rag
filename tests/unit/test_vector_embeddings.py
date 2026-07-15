from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from private_rag.vector.embeddings import SentenceTransformersEmbeddingProvider


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
