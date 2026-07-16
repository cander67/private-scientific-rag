from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
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
from private_rag.search.service import FTS_TABLE
from private_rag.vector.embeddings import DeterministicEmbeddingProvider
from private_rag.vector.models import EmbeddingRun
from private_rag.vector.store import InMemoryVectorStore


class _FakeLLM:
    def __init__(self) -> None:
        self.calls: list[list[ChatMessage]] = []
        self.complete_models: list[str] = []
        self.smoke_models: list[str] = []

    def complete(self, *, model: str, messages: list[ChatMessage]) -> ChatCompletion:
        self.complete_models.append(model)
        self.calls.append(messages)
        return ChatCompletion(content="LiFePO4 is discussed in the repository [1].", model=model)

    def smoke(self, *, model: str) -> ChatCompletion:
        self.smoke_models.append(model)
        return ChatCompletion(content="local model ready [1]", model=model)


class _FakeReranker:
    def score(
        self,
        query: str,
        results: list[RetrievalSearchResult],
        model_name: str,
    ) -> list[float]:
        return [1.0 - index * 0.01 for index, _ in enumerate(results)]


def _client_with_chat_fakes_and_database() -> tuple[TestClient, _FakeLLM, sessionmaker[Session]]:
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
    return TestClient(app), llm, session_factory


def _client_with_chat_fakes() -> tuple[TestClient, _FakeLLM]:
    client, llm, _ = _client_with_chat_fakes_and_database()
    return client, llm


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
    registry_models = registry_response.json()["models"]
    assert "gemma3:4b" in {model["name"] for model in registry_models}
    default_model = next(model for model in registry_models if model["name"] == "gemma3:4b")
    assert default_model["role"] == "recommended_default"
    assert default_model["setup_command"] == "ollama pull gemma3:4b"
    assert default_model["readiness_required"] is True
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


def test_chat_question_updates_session_retrieval_settings() -> None:
    client, _ = _client_with_chat_fakes()
    repository_id = _default_repository_id(client)
    client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "chat-settings.txt",
                b"Abstract\nLiFePO4 cathodes retain capacity during cycling.\n",
                "text/plain",
            )
        },
    )
    client.post(f"/repositories/{repository_id}/full-text/rebuild")
    client.post(f"/repositories/{repository_id}/vector/rebuild")
    session_response = client.post(
        f"/repositories/{repository_id}/chat/sessions",
        json={
            "title": "Retrieval controls",
            "retrieval_settings": {
                "mode": "hybrid",
                "top_k": 3,
                "reranker_strategy": "none",
            },
        },
    )

    chat_session_id = session_response.json()["id"]
    response = client.post(
        f"/repositories/{repository_id}/chat/sessions/{chat_session_id}/messages",
        json={
            "content": "What does the repository say about LiFePO4?",
            "retrieval_settings": {
                "mode": "hybrid",
                "top_k": 5,
                "reranker_strategy": "cross_encoder",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["session"]["retrieval_settings"] == {
        "mode": "hybrid",
        "top_k": 5,
        "reranker_strategy": "cross_encoder",
    }


def test_chat_readiness_reports_index_and_model_state() -> None:
    client, _ = _client_with_chat_fakes()
    repository_id = _default_repository_id(client)

    initial_response = client.get(f"/repositories/{repository_id}/chat/readiness")
    client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "chat-readiness.txt",
                b"Abstract\nLiFePO4 cathodes retain capacity during cycling.\n",
                "text/plain",
            )
        },
    )
    client.post(f"/repositories/{repository_id}/full-text/rebuild")
    client.post(f"/repositories/{repository_id}/vector/rebuild")
    ready_response = client.get(f"/repositories/{repository_id}/chat/readiness")

    assert initial_response.status_code == 200
    assert initial_response.json()["parsed_chunks"] == 0
    assert (
        initial_response.json()["full_text"]["message"] == "No parsed chunks are available to index"
    )
    assert initial_response.json()["full_text"]["ready"] is False
    assert initial_response.json()["full_text"]["status"] == "missing"
    assert (
        initial_response.json()["vector"]["message"]
        == "No parsed chunks are available to embed/index"
    )
    assert initial_response.json()["vector"]["ready"] is False
    assert initial_response.json()["vector"]["status"] == "missing"
    assert initial_response.json()["local_model"]["ready"] is True
    assert initial_response.json()["ready_for_chat"] is False
    assert ready_response.status_code == 200
    assert ready_response.json()["parsed_chunks"] == 1
    assert ready_response.json()["full_text"]["ready"] is True
    assert ready_response.json()["full_text"]["status"] == "ready"
    assert ready_response.json()["vector"]["ready"] is True
    assert ready_response.json()["vector"]["status"] == "ready"
    assert ready_response.json()["ready_for_chat"] is True


def test_chat_readiness_uses_repository_chat_model() -> None:
    client, llm = _client_with_chat_fakes()
    repository_response = client.get("/repositories/default")
    repository_id = repository_response.json()["repository"]["id"]
    settings = repository_response.json()["settings"]
    settings["model"]["ollama_chat_model"] = "gemma3:custom"
    settings["embedding"]["model"] = "test-deterministic"
    settings["vector"]["vector_size"] = 8
    update_response = client.put(
        f"/repositories/{repository_id}/settings",
        json={"settings": settings},
    )

    response = client.get(f"/repositories/{repository_id}/chat/readiness")

    assert update_response.status_code == 200
    assert response.status_code == 200
    assert response.json()["local_model"]["model"] == "gemma3:custom"
    assert llm.complete_models == []
    assert llm.smoke_models == ["gemma3:custom"]


def test_chat_session_custom_model_reaches_llm_boundary() -> None:
    client, llm = _client_with_chat_fakes()
    repository_id = _default_repository_id(client)
    client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "chat-custom-model.txt",
                b"Abstract\nLiFePO4 cathodes retain capacity during cycling.\n",
                "text/plain",
            )
        },
    )
    client.post(f"/repositories/{repository_id}/full-text/rebuild")
    client.post(f"/repositories/{repository_id}/vector/rebuild")
    session_response = client.post(
        f"/repositories/{repository_id}/chat/sessions",
        json={"title": "Custom local model", "model": "qwen-local:custom"},
    )

    chat_session_id = session_response.json()["id"]
    response = client.post(
        f"/repositories/{repository_id}/chat/sessions/{chat_session_id}/messages",
        json={"content": "What does the repository say about LiFePO4?"},
    )

    assert session_response.status_code == 200
    assert session_response.json()["model"] == "qwen-local:custom"
    assert response.status_code == 200
    assert response.json()["session"]["model"] == "qwen-local:custom"
    assert llm.complete_models == ["qwen-local:custom"]


def test_chat_readiness_distinguishes_parsed_but_unindexed_repository() -> None:
    client, _ = _client_with_chat_fakes()
    repository_id = _default_repository_id(client)
    client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "chat-unindexed.txt",
                b"Abstract\nLiFePO4 cathodes retain capacity during cycling.\n",
                "text/plain",
            )
        },
    )

    response = client.get(f"/repositories/{repository_id}/chat/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed_chunks"] == 1
    assert payload["full_text"]["ready"] is False
    assert payload["full_text"]["status"] == "missing"
    assert payload["full_text"]["message"] == "Full-text index has not been rebuilt"
    assert payload["vector"]["ready"] is False
    assert payload["vector"]["status"] == "missing"
    assert payload["vector"]["message"] == "Vector index has not been rebuilt"
    assert payload["ready_for_chat"] is False


def test_chat_readiness_reports_partial_and_stale_indexes() -> None:
    client, _, session_factory = _client_with_chat_fakes_and_database()
    repository_id = _default_repository_id(client)
    client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "chat-indexed.txt",
                b"Abstract\nThe first indexed chunk mentions LiFePO4.\n",
                "text/plain",
            )
        },
    )
    client.post(f"/repositories/{repository_id}/full-text/rebuild")
    client.post(f"/repositories/{repository_id}/vector/rebuild")
    client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "chat-unindexed-new.txt",
                b"Abstract\nThe second parsed chunk is not indexed yet.\n",
                "text/plain",
            )
        },
    )

    partial_response = client.get(f"/repositories/{repository_id}/chat/readiness")
    with session_factory() as session:
        for index in range(2):
            session.execute(
                text(
                    f"""
                    INSERT INTO {FTS_TABLE} (
                        repository_id, document_id, document_version_id, chunk_id, chunk_index,
                        document_title, section, source_type, document_kind, tags,
                        has_table, has_figure, patent_sections,
                        page_start, page_end, line_start, line_end,
                        title, headings, body, captions, tables, claims, examples
                    )
                    VALUES (
                        :repository_id, :document_id, :document_version_id, :chunk_id, :chunk_index,
                        :document_title, :section, :source_type, :document_kind, :tags,
                        :has_table, :has_figure, :patent_sections,
                        :page_start, :page_end, :line_start, :line_end,
                        :title, :headings, :body, :captions, :tables, :claims, :examples
                    )
                    """
                ),
                {
                    "repository_id": repository_id,
                    "document_id": f"stale-document-{index}",
                    "document_version_id": f"stale-version-{index}",
                    "chunk_id": f"stale-chunk-{index}",
                    "chunk_index": 100 + index,
                    "document_title": "stale.txt",
                    "section": "Abstract",
                    "source_type": "text",
                    "document_kind": None,
                    "tags": "",
                    "has_table": 0,
                    "has_figure": 0,
                    "patent_sections": "",
                    "page_start": None,
                    "page_end": None,
                    "line_start": 1,
                    "line_end": 1,
                    "title": "stale.txt",
                    "headings": "Abstract",
                    "body": "Stale indexed chunk",
                    "captions": "",
                    "tables": "",
                    "claims": "",
                    "examples": "",
                },
            )
        embedding_run = session.scalar(
            text("SELECT id FROM embedding_runs WHERE repository_id = :repository_id"),
            {"repository_id": repository_id},
        )
        assert embedding_run is not None
        session.query(EmbeddingRun).filter(EmbeddingRun.repository_id == repository_id).update(
            {"chunk_count": 3}
        )
        session.commit()
    stale_response = client.get(f"/repositories/{repository_id}/chat/readiness")

    assert partial_response.status_code == 200
    partial_payload = partial_response.json()
    assert partial_payload["parsed_chunks"] == 2
    assert partial_payload["full_text"]["ready"] is False
    assert partial_payload["full_text"]["status"] == "partial"
    assert partial_payload["full_text"]["message"] == "1 of 2 full-text chunks indexed"
    assert partial_payload["vector"]["ready"] is False
    assert partial_payload["vector"]["status"] == "partial"
    assert partial_payload["vector"]["message"] == "1 of 2 vector chunks indexed"
    assert partial_payload["ready_for_chat"] is False

    assert stale_response.status_code == 200
    stale_payload = stale_response.json()
    assert stale_payload["parsed_chunks"] == 2
    assert stale_payload["full_text"]["ready"] is False
    assert stale_payload["full_text"]["status"] == "stale"
    assert "rebuild recommended" in stale_payload["full_text"]["message"]
    assert stale_payload["vector"]["ready"] is False
    assert stale_payload["vector"]["status"] == "stale"
    assert "rebuild recommended" in stale_payload["vector"]["message"]
    assert stale_payload["ready_for_chat"] is False


def test_chat_sessions_can_be_deleted_individually_and_cleared() -> None:
    client, _ = _client_with_chat_fakes()
    repository_id = _default_repository_id(client)
    first = client.post(
        f"/repositories/{repository_id}/chat/sessions",
        json={"title": "First"},
    ).json()
    second = client.post(
        f"/repositories/{repository_id}/chat/sessions",
        json={"title": "Second"},
    ).json()

    delete_response = client.delete(f"/repositories/{repository_id}/chat/sessions/{first['id']}")
    after_delete = client.get(f"/repositories/{repository_id}/chat/sessions")
    clear_response = client.delete(f"/repositories/{repository_id}/chat/sessions")
    after_clear = client.get(f"/repositories/{repository_id}/chat/sessions")

    assert second["id"]
    assert delete_response.status_code == 204
    assert [session["title"] for session in after_delete.json()] == ["Second"]
    assert clear_response.status_code == 204
    assert after_clear.json() == []
