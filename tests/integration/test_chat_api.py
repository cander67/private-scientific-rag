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
from private_rag.retrieval.schemas import RetrievalSearchResult
from private_rag.vector.embeddings import DeterministicEmbeddingProvider
from private_rag.vector.store import InMemoryVectorStore


class _FakeLLM:
    def __init__(self) -> None:
        self.calls: list[list[ChatMessage]] = []

    def complete(self, *, model: str, messages: list[ChatMessage]) -> ChatCompletion:
        self.calls.append(messages)
        return ChatCompletion(content="LiFePO4 is discussed in the repository [1].", model=model)

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


def _client_with_chat_fakes() -> tuple[TestClient, _FakeLLM]:
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


def _default_repository_id(client: TestClient) -> str:
    response = client.get("/repositories/default")
    payload = response.json()
    settings = payload["settings"]
    settings["embedding"]["model"] = "test-deterministic"
    settings["vector"]["vector_size"] = 8
    update_response = client.put(
        f"/repositories/{payload['repository']['id']}/settings",
        json={"settings": settings},
    )
    assert update_response.status_code == 200
    return str(payload["repository"]["id"])


def test_chat_model_registry_and_smoke_use_llm_boundary() -> None:
    client, _ = _client_with_chat_fakes()
    repository_id = _default_repository_id(client)

    registry_response = client.get(f"/repositories/{repository_id}/chat/models")
    smoke_response = client.post(f"/repositories/{repository_id}/chat/models/smoke")

    assert registry_response.status_code == 200
    assert registry_response.json()["default_model"] == "gemma3:4b"
    assert "gemma3:4b" in {model["name"] for model in registry_response.json()["models"]}
    assert smoke_response.status_code == 200
    assert smoke_response.json()["response"] == "local model ready [1]"


def test_chat_session_persists_messages_and_mapped_citations() -> None:
    client, llm = _client_with_chat_fakes()
    repository_id = _default_repository_id(client)
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "chat-materials.txt",
                b"Abstract\nLiFePO4 cathodes retain capacity during cycling.\n",
                "text/plain",
            )
        },
    )
    full_text_rebuild = client.post(f"/repositories/{repository_id}/full-text/rebuild")
    vector_rebuild = client.post(f"/repositories/{repository_id}/vector/rebuild")
    session_response = client.post(
        f"/repositories/{repository_id}/chat/sessions",
        json={"title": "Cathode review"},
    )

    chat_session_id = session_response.json()["id"]
    question_response = client.post(
        f"/repositories/{repository_id}/chat/sessions/{chat_session_id}/messages",
        json={"content": "What does the repository say about LiFePO4?"},
    )
    reload_response = client.get(
        f"/repositories/{repository_id}/chat/sessions/{chat_session_id}",
    )

    assert upload_response.status_code == 200
    assert full_text_rebuild.status_code == 200
    assert vector_rebuild.status_code == 200
    assert session_response.status_code == 200
    assert question_response.status_code == 200
    payload = question_response.json()
    assert payload["session"]["retrieval_settings"]["mode"] == "hybrid"
    assert payload["assistant_message"]["content"].endswith("[1].")
    assert payload["assistant_message"]["retrieval_run_id"]
    citation = payload["assistant_message"]["citations"][0]
    assert citation["chunk_id"] == upload_response.json()["chunks_preview"][0]["id"]
    assert citation["document_title"] == "chat-materials.txt"
    assert citation["retrieval_rank"] == 1
    assert llm.calls
    assert "Repository context follows" in llm.calls[0][0].content
    assert "[1] chat-materials.txt" in llm.calls[0][0].content

    assert reload_response.status_code == 200
    assert [message["role"] for message in reload_response.json()["messages"]] == [
        "user",
        "assistant",
    ]
