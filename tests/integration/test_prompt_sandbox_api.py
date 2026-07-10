from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.api.app import create_app
from private_rag.api.routes.chat import get_chat_llm
from private_rag.api.routes.repositories import get_db_session
from private_rag.api.routes.retrieval import get_reranker_provider
from private_rag.api.routes.vector import get_embedding_provider, get_vector_store
from private_rag.chat.llm import ChatCompletion, ChatMessage
from private_rag.db.base import Base
from private_rag.repositories import models as repository_models  # noqa: F401
from private_rag.retrieval.schemas import RetrievalSearchResult
from private_rag.vector.embeddings import DeterministicEmbeddingProvider
from private_rag.vector.store import InMemoryVectorStore


class _FakeLLM:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[ChatMessage]]] = []

    def complete(self, *, model: str, messages: list[ChatMessage]) -> ChatCompletion:
        self.calls.append((model, messages))
        return ChatCompletion(
            content="LiFePO4 retains capacity during cycling [1].",
            model=model,
        )

    def smoke(self, *, model: str) -> ChatCompletion:
        return ChatCompletion(content="local model ready [1]", model=model)


class _FakeReranker:
    def score(
        self,
        query: str,
        results: list[RetrievalSearchResult],
        model_name: str,
    ) -> list[float]:
        return [1.0 - index * 0.01 for index, _ in enumerate(results)]


def _client_with_database() -> tuple[TestClient, _FakeLLM]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    store = InMemoryVectorStore()
    embedder = DeterministicEmbeddingProvider(vector_size=8)
    llm = _FakeLLM()

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedding_provider] = lambda: embedder
    app.dependency_overrides[get_reranker_provider] = lambda: _FakeReranker()
    app.dependency_overrides[get_chat_llm] = lambda: llm
    return TestClient(app), llm


def test_sandbox_prompt_versions_copy_to_and_from_chat_library_without_changing_defaults() -> None:
    client, _ = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    original_active_prompt_id = created["settings"]["prompt"]["active_chat_prompt_id"]
    chat_prompt_id = created["settings"]["prompt"]["library"][0]["id"]

    create_response = client.post(
        f"/repositories/{repository_id}/prompt-sandbox/prompts",
        json={
            "name": "Sandbox citation prompt",
            "notes": "Try stricter evidence language.",
            "source_chat_prompt_id": chat_prompt_id,
        },
    )

    assert create_response.status_code == 200
    prompt = create_response.json()
    assert prompt["name"] == "Sandbox citation prompt"
    assert prompt["notes"] == "Try stricter evidence language."
    assert prompt["body"] == created["settings"]["prompt"]["library"][0]["text"]
    assert prompt["source_chat_prompt_id"] == chat_prompt_id
    assert prompt["used_by_run"] is False

    list_response = client.get(f"/repositories/{repository_id}/prompt-sandbox/prompts")
    read_response = client.get(
        f"/repositories/{repository_id}/prompt-sandbox/prompts/{prompt['id']}"
    )

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [prompt["id"]]
    assert read_response.status_code == 200
    assert read_response.json()["body"] == prompt["body"]

    copy_response = client.post(
        f"/repositories/{repository_id}/prompt-sandbox/prompts/{prompt['id']}/copy-to-chat-library",
        json={"name": "Vetted sandbox prompt"},
    )
    settings_response = client.get(f"/repositories/{repository_id}/settings")

    assert copy_response.status_code == 200
    copied = copy_response.json()
    settings = settings_response.json()["settings"]
    assert copied["id"] != original_active_prompt_id
    assert copied["name"] == "Vetted sandbox prompt"
    assert copied["text"] == prompt["body"]
    assert settings["prompt"]["active_chat_prompt_id"] == original_active_prompt_id
    assert any(entry["id"] == copied["id"] for entry in settings["prompt"]["library"])


def test_sandbox_run_persists_prompt_snapshot_context_answer_and_citations() -> None:
    client, llm = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    settings = created["settings"]
    settings["embedding"]["model"] = "test-deterministic"
    settings["vector"]["vector_size"] = 8
    assert (
        client.put(
            f"/repositories/{repository_id}/settings",
            json={"settings": settings},
        ).status_code
        == 200
    )
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "sandbox-materials.txt",
                b"Abstract\nLiFePO4 cathodes retain capacity during cycling.\n",
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 200
    assert client.post(f"/repositories/{repository_id}/full-text/rebuild").status_code == 200
    assert client.post(f"/repositories/{repository_id}/vector/rebuild").status_code == 200
    prompt_response = client.post(
        f"/repositories/{repository_id}/prompt-sandbox/prompts",
        json={
            "name": "Strict citation prompt",
            "body": "Answer only from retrieved context and cite each factual claim.",
        },
    )
    assert prompt_response.status_code == 200
    prompt = prompt_response.json()

    run_response = client.post(
        f"/repositories/{repository_id}/prompt-sandbox/runs",
        json={
            "prompt_version_id": prompt["id"],
            "query": "What does the repository say about LiFePO4 cycling?",
            "model": "gemma3:4b",
            "retrieval_settings": {
                "mode": "hybrid",
                "top_k": 3,
                "reranker_strategy": "cross_encoder",
            },
        },
    )

    assert run_response.status_code == 200
    run = run_response.json()
    assert run["status"] == "completed"
    assert run["prompt_version_id"] == prompt["id"]
    assert run["prompt_snapshot"]["body"] == prompt["body"]
    assert run["model"] == "gemma3:4b"
    assert run["answer"] == "LiFePO4 retains capacity during cycling [1]."
    assert run["retrieval_run_id"]
    assert run["latency_ms"] >= 0
    assert run["retrieval_settings"]["mode"] == "hybrid"
    assert run["context_entries"][0]["document_title"] == "sandbox-materials.txt"
    assert (
        run["context_entries"][0]["chunk_id"] == upload_response.json()["chunks_preview"][0]["id"]
    )
    assert run["context_entries"][0]["score_breakdown"]["rerank"] is not None
    assert run["citations"][0]["chunk_id"] == upload_response.json()["chunks_preview"][0]["id"]
    assert llm.calls[0][0] == "gemma3:4b"
    assert "Answer only from retrieved context" in llm.calls[0][1][0].content
    assert "[1] sandbox-materials.txt" in llm.calls[0][1][0].content

    reload_response = client.get(
        f"/repositories/{repository_id}/prompt-sandbox/runs/{run['id']}",
    )

    assert reload_response.status_code == 200
    reloaded = reload_response.json()
    assert reloaded["prompt_snapshot"] == run["prompt_snapshot"]
    assert reloaded["context_entries"] == run["context_entries"]
    assert reloaded["answer"] == run["answer"]


def test_sandbox_comparison_runs_same_query_across_retrieval_configs() -> None:
    client, llm = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    settings = created["settings"]
    settings["embedding"]["model"] = "test-deterministic"
    settings["vector"]["vector_size"] = 8
    assert (
        client.put(
            f"/repositories/{repository_id}/settings",
            json={"settings": settings},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/repositories/{repository_id}/documents",
            files={
                "file": (
                    "comparison-materials.txt",
                    (
                        b"Abstract\n"
                        b"LiFePO4 cathodes retain capacity during cycling.\n"
                        b"Methods\n"
                        b"Conductive carbon improves LiFePO4 electrode performance.\n"
                    ),
                    "text/plain",
                )
            },
        ).status_code
        == 200
    )
    assert client.post(f"/repositories/{repository_id}/full-text/rebuild").status_code == 200
    assert client.post(f"/repositories/{repository_id}/vector/rebuild").status_code == 200
    prompt_response = client.post(
        f"/repositories/{repository_id}/prompt-sandbox/prompts",
        json={
            "name": "Comparison prompt",
            "body": "Answer only from retrieved context and cite each factual claim.",
        },
    )
    assert prompt_response.status_code == 200
    prompt = prompt_response.json()

    comparison_response = client.post(
        f"/repositories/{repository_id}/prompt-sandbox/comparisons",
        json={
            "query": "LiFePO4 cathodes retain capacity cycling",
            "runs": [
                {
                    "label": "Full-text",
                    "prompt_version_id": prompt["id"],
                    "model": "gemma3:4b",
                    "retrieval_settings": {
                        "mode": "full_text",
                        "top_k": 3,
                        "reranker_strategy": "none",
                    },
                },
                {
                    "label": "Vector",
                    "prompt_version_id": prompt["id"],
                    "model": "gemma3:4b",
                    "retrieval_settings": {
                        "mode": "vector",
                        "top_k": 3,
                        "reranker_strategy": "none",
                    },
                },
                {
                    "label": "Hybrid",
                    "prompt_version_id": prompt["id"],
                    "model": "gemma3:4b",
                    "retrieval_settings": {
                        "mode": "hybrid",
                        "top_k": 3,
                        "reranker_strategy": "none",
                    },
                },
                {
                    "label": "Reranked hybrid",
                    "prompt_version_id": prompt["id"],
                    "model": "gemma3:4b",
                    "retrieval_settings": {
                        "mode": "hybrid",
                        "top_k": 3,
                        "reranker_strategy": "cross_encoder",
                    },
                },
            ],
        },
    )

    assert comparison_response.status_code == 200
    comparison = comparison_response.json()
    assert comparison["query"] == "LiFePO4 cathodes retain capacity cycling"
    assert comparison["status"] == "completed"
    assert [run["label"] for run in comparison["runs"]] == [
        "Full-text",
        "Vector",
        "Hybrid",
        "Reranked hybrid",
    ]
    assert {run["retrieval_settings"]["mode"] for run in comparison["runs"]} == {
        "full_text",
        "vector",
        "hybrid",
    }
    assert comparison["runs"][3]["retrieval_settings"]["reranker_strategy"] == "cross_encoder"
    assert all(run["comparison_id"] == comparison["id"] for run in comparison["runs"])
    assert all(run["answer"].endswith("[1].") for run in comparison["runs"])
    assert all(run["context_entries"] for run in comparison["runs"])
    assert len(llm.calls) == 4

    reload_response = client.get(
        f"/repositories/{repository_id}/prompt-sandbox/comparisons/{comparison['id']}",
    )

    assert reload_response.status_code == 200
    assert reload_response.json()["runs"] == comparison["runs"]
