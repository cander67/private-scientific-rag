from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.api.app import create_app
from private_rag.api.routes.chat import get_chat_llm
from private_rag.api.routes.repositories import get_db_session
from private_rag.api.routes.retrieval import get_reranker_provider
from private_rag.api.routes.vector import get_embedding_provider, get_vector_store
from private_rag.chat.llm import OllamaChatLLM
from private_rag.core.settings import get_settings
from private_rag.db.base import Base
from private_rag.retrieval.schemas import RetrievalSearchResult
from private_rag.vector.embeddings import DeterministicEmbeddingProvider
from private_rag.vector.store import InMemoryVectorStore


class _StableLiveReranker:
    def score(
        self,
        query: str,
        results: list[RetrievalSearchResult],
        model_name: str,
    ) -> list[float]:
        return [1.0 - index * 0.01 for index, _ in enumerate(results)]


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1")
def test_chat_rag_live_with_ollama_and_fixture_repository() -> None:
    settings = get_settings()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    store = InMemoryVectorStore()

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedding_provider] = lambda: DeterministicEmbeddingProvider(
        vector_size=8
    )
    app.dependency_overrides[get_reranker_provider] = lambda: _StableLiveReranker()
    app.dependency_overrides[get_chat_llm] = lambda: OllamaChatLLM(
        base_url=settings.ollama_base_url,
        timeout=180,
    )
    client = TestClient(app)

    repository_payload = client.get("/repositories/default").json()
    repository_id = repository_payload["repository"]["id"]
    repository_settings = repository_payload["settings"]
    repository_settings["embedding"]["model"] = "test-deterministic"
    repository_settings["vector"]["vector_size"] = 8
    settings_response = client.put(
        f"/repositories/{repository_id}/settings",
        json={"settings": repository_settings},
    )
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "live-chat-fixture.txt",
                b"Abstract\nThe live fixture reports that cobalt-free LiFePO4 retained 92 percent capacity.\n",
                "text/plain",
            )
        },
    )
    full_text_response = client.post(f"/repositories/{repository_id}/full-text/rebuild")
    vector_response = client.post(f"/repositories/{repository_id}/vector/rebuild")
    session_response = client.post(
        f"/repositories/{repository_id}/chat/sessions",
        json={"title": "Live local RAG smoke"},
    )
    chat_session_id = session_response.json()["id"]
    question_response = client.post(
        f"/repositories/{repository_id}/chat/sessions/{chat_session_id}/messages",
        json={
            "content": (
                "According to the repository context, what capacity retention was reported? "
                "Answer in one sentence and cite the source."
            )
        },
    )

    assert settings_response.status_code == 200
    assert upload_response.status_code == 200
    assert full_text_response.status_code == 200
    assert vector_response.status_code == 200
    assert session_response.status_code == 200
    assert question_response.status_code == 200
    assistant = question_response.json()["assistant_message"]
    assert assistant["content"].strip()
    assert assistant["citations"]
