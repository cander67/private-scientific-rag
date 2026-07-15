from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.api.app import create_app
from private_rag.api.routes.repositories import (
    get_admin_vector_store,
    get_db_session,
    get_settings_chat_llm,
    get_settings_readiness_checker,
)
from private_rag.chat.llm import ChatCompletion, ChatMessage
from private_rag.chat.models import ChatMessageRow, ChatSession
from private_rag.core.settings import get_settings
from private_rag.db.base import Base
from private_rag.ingestion.models import Document, DocumentChunk, DocumentVersion
from private_rag.prompt_sandbox.models import SandboxComparison, SandboxRun
from private_rag.repositories import models as repository_models  # noqa: F401
from private_rag.repositories.models import Repository, RepositorySnapshot
from private_rag.repositories.schemas import RepositorySettingsReadinessItem
from private_rag.retrieval.models import RetrievalRun
from private_rag.search.service import rebuild_full_text_index
from private_rag.vector.models import EmbeddingRun
from private_rag.vector.store import InMemoryVectorStore, VectorStoreError


def _client_with_database() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.state.test_session_factory = session_factory
    return TestClient(app)


def test_default_repository_is_created_on_first_request() -> None:
    client = _client_with_database()

    response = client.get("/repositories/default")

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository"]["name"] == "Default Repository"
    assert payload["settings"]["chunking"]["chunk_size"] == 800
    assert payload["settings"]["embedding"]["model"]


def test_repository_list_includes_default_repository() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()

    response = client.get("/repositories")

    assert response.status_code == 200
    assert response.json() == [created["repository"]]


def test_repository_settings_round_trip_and_manifest_export() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    settings = created["settings"]
    settings["chunking"]["chunk_size"] = 1200
    settings["chunking"]["chunk_overlap"] = 160
    settings["full_text"]["tokenizer"] = "porter"
    settings["full_text"]["porter_stemming"] = True
    settings["prompt"]["version"] = "science-v2"

    update_response = client.put(
        f"/repositories/{repository_id}/settings",
        json={"settings": settings},
    )
    manifest_response = client.get(f"/repositories/{repository_id}/manifest")

    assert update_response.status_code == 200
    assert update_response.json()["settings"]["prompt"]["version"] == "science-v2"
    assert manifest_response.status_code == 200
    manifest = manifest_response.json()
    assert manifest["settings"]["chunking"]["chunk_size"] == 1200
    assert manifest["settings"]["parser"]["structured_parser"]
    assert manifest["settings"]["full_text"]["tokenizer"] == "porter"
    assert manifest["settings"]["full_text"]["porter_stemming"] is True


def test_repository_settings_save_creates_snapshot_and_stays_scoped() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]

    test_app = cast(Any, client.app)
    with test_app.state.test_session_factory() as session:
        other_repository = Repository(name="Other Repository")
        session.add(other_repository)
        session.flush()
        other_settings = deepcopy(created["settings"])
        other_settings["chunking"] = {
            **created["settings"]["chunking"],
            "chunk_size": 777,
        }
        other_repository.settings = repository_models.RepositorySettingsRow(settings=other_settings)
        session.commit()
        other_repository_id = other_repository.id

    settings = created["settings"]
    settings["chunking"]["chunk_size"] = 1400

    response = client.put(
        f"/repositories/{repository_id}/settings",
        json={"settings": settings},
    )

    assert response.status_code == 200
    assert (
        client.get(f"/repositories/{repository_id}/settings").json()["settings"]["chunking"][
            "chunk_size"
        ]
        == 1400
    )
    assert (
        client.get(f"/repositories/{other_repository_id}/settings").json()["settings"]["chunking"][
            "chunk_size"
        ]
        == 777
    )
    with test_app.state.test_session_factory() as session:
        snapshots = session.query(RepositorySnapshot).filter_by(repository_id=repository_id).all()
        assert len(snapshots) == 1
        assert snapshots[0].manifest["settings"]["chunking"]["chunk_size"] == 1400


def test_repository_settings_endpoint_rejects_invalid_settings() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    settings = created["settings"]
    settings["chunking"]["chunk_overlap"] = settings["chunking"]["chunk_size"]

    response = client.put(
        f"/repositories/{repository_id}/settings",
        json={"settings": settings},
    )

    assert response.status_code == 422
    assert "chunk_overlap must be smaller" in response.text


def test_repository_settings_impact_endpoint_reports_categories() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    settings = created["settings"]
    settings["chunking"]["mode"] = "fixed"
    settings["embedding"]["model"] = "sentence-transformers/other"
    settings["reranking"]["model"] = "cross-encoder/other"
    settings["export"]["include_sources"] = False

    response = client.post(
        f"/repositories/{repository_id}/settings/impact",
        json={"settings": settings},
    )

    assert response.status_code == 200
    payload = response.json()
    categories = {impact["category"] for impact in payload["impacts"]}
    assert payload["has_changes"] is True
    assert "document_reprocessing" in categories
    assert "vector_rebuild" in categories
    assert "retrieval_defaults" in categories
    assert "export_recreate" in categories


class FakeSettingsLLM:
    def complete(self, *, model: str, messages: list[ChatMessage]) -> ChatCompletion:
        return ChatCompletion(content="local model ready [1]", model=model)

    def smoke(self, *, model: str) -> ChatCompletion:
        return ChatCompletion(content="local model ready [1]", model=model)


class FakeSettingsReadinessChecker:
    def check_qdrant(
        self, *, qdrant_url: str, collection_name: str
    ) -> RepositorySettingsReadinessItem:
        return RepositorySettingsReadinessItem(
            target="qdrant",
            label="Qdrant",
            status="unavailable_runtime",
            ready=False,
            message="Qdrant is not reachable from this test runtime.",
            model=collection_name,
        )

    def check_chat(
        self,
        *,
        llm: FakeSettingsLLM,
        model: str,
    ) -> RepositorySettingsReadinessItem:
        completion = llm.smoke(model=model)
        return RepositorySettingsReadinessItem(
            target="chat",
            label="Chat model",
            status="ready",
            ready=True,
            message=f"{completion.model} responded.",
            model=completion.model,
        )

    def check_embedding(
        self,
        *,
        provider: str,
        model: str,
        expected_vector_size: int,
    ) -> RepositorySettingsReadinessItem:
        return RepositorySettingsReadinessItem(
            target="embedding",
            label="Embedding model",
            status="not_installed",
            ready=False,
            message=f"{model} is not cached locally.",
            model=model,
        )

    def check_reranker(
        self,
        *,
        strategy: str,
        model: str | None,
    ) -> RepositorySettingsReadinessItem:
        return RepositorySettingsReadinessItem(
            target="reranker",
            label="Reranker",
            status="skipped",
            ready=True,
            message="Reranking is disabled for this repository.",
            model=model,
        )


class FailingDeleteVectorStore(InMemoryVectorStore):
    def delete_collection(self, collection_name: str) -> None:
        raise VectorStoreError("Qdrant is unavailable in this test runtime.")


def test_repository_settings_readiness_endpoint_uses_mocked_boundaries() -> None:
    client = _client_with_database()
    app = cast(Any, client.app)
    app.dependency_overrides[get_settings_chat_llm] = lambda: FakeSettingsLLM()
    app.dependency_overrides[get_settings_readiness_checker] = lambda: (
        FakeSettingsReadinessChecker()
    )
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    settings = created["settings"]
    settings["reranking"] = {"strategy": "none", "model": None}
    client.put(f"/repositories/{repository_id}/settings", json={"settings": settings})

    response = client.post(f"/repositories/{repository_id}/settings/readiness")

    assert response.status_code == 200
    payload = response.json()
    statuses = {item["target"]: item["status"] for item in payload["items"]}
    assert payload["checked"] is True
    assert statuses == {
        "qdrant": "unavailable_runtime",
        "chat": "ready",
        "embedding": "not_installed",
        "reranker": "skipped",
    }


def test_repository_summary_returns_empty_counts_and_mocked_readiness() -> None:
    client = _client_with_database()
    _install_readiness_fakes(client)
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    settings = created["settings"]
    settings["reranking"] = {"strategy": "none", "model": None}
    client.put(f"/repositories/{repository_id}/settings", json={"settings": settings})

    response = client.get(f"/repositories/{repository_id}/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository"]["id"] == repository_id
    assert payload["counts"] == {
        "documents": 0,
        "parsed_documents": 0,
        "chunks": 0,
        "chat_sessions": 0,
        "chat_messages": 0,
        "retrieval_runs": 0,
        "sandbox_runs": 0,
        "sandbox_comparisons": 0,
        "exports": 0,
        "recreate_events": 0,
    }
    assert payload["full_text"]["status"] == "missing"
    assert payload["vector"]["status"] == "missing"
    statuses = {item["target"]: item["status"] for item in payload["settings_readiness"]["items"]}
    assert statuses == {
        "qdrant": "unavailable_runtime",
        "chat": "ready",
        "embedding": "not_installed",
        "reranker": "skipped",
    }
    assert payload["active_config"]["chat_model"] == settings["model"]["ollama_chat_model"]
    assert payload["warnings"]


def test_repository_summary_counts_are_repository_scoped() -> None:
    client = _client_with_database()
    _install_readiness_fakes(client)
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    test_app = cast(Any, client.app)
    with test_app.state.test_session_factory() as session:
        other_repository = Repository(name="Other Repository")
        session.add(other_repository)
        session.flush()
        other_repository.settings = repository_models.RepositorySettingsRow(
            settings=created["settings"]
        )
        _add_document_with_chunks(session, repository_id, "dashboard.txt", 2)
        _add_document_with_chunks(session, other_repository.id, "other.txt", 1)
        session.commit()
        rebuild_full_text_index(session, repository_id)
        session.add(
            EmbeddingRun(
                repository_id=repository_id,
                provider="sentence_transformers",
                model="test-deterministic",
                vector_size=8,
                distance="cosine",
                collection_name="default_repository",
                status="indexed",
                chunk_count=2,
                settings_snapshot={},
            )
        )
        session.add(
            EmbeddingRun(
                repository_id=other_repository.id,
                provider="sentence_transformers",
                model="other",
                vector_size=8,
                distance="cosine",
                collection_name="other",
                status="indexed",
                chunk_count=1,
                settings_snapshot={},
            )
        )
        chat_session = ChatSession(
            repository_id=repository_id,
            title="Dashboard chat",
            model="local",
            retrieval_settings={},
            prompt_id="rag-chat-default-v1",
        )
        other_chat_session = ChatSession(
            repository_id=other_repository.id,
            title="Other chat",
            model="local",
            retrieval_settings={},
            prompt_id="rag-chat-default-v1",
        )
        session.add_all([chat_session, other_chat_session])
        session.flush()
        session.add(
            ChatMessageRow(
                session_id=chat_session.id,
                repository_id=repository_id,
                sequence=1,
                role="user",
                content="What changed?",
            )
        )
        session.add(
            RetrievalRun(
                repository_id=repository_id,
                mode="hybrid",
                query="dashboard",
                filters={},
                top_k=5,
                candidate_pool_size=25,
                rrf_constant=60,
                reranker_strategy="none",
                metadata_boosts={},
                settings_snapshot={},
            )
        )
        session.add(
            RetrievalRun(
                repository_id=other_repository.id,
                mode="hybrid",
                query="other",
                filters={},
                top_k=5,
                candidate_pool_size=25,
                rrf_constant=60,
                reranker_strategy="none",
                metadata_boosts={},
                settings_snapshot={},
            )
        )
        session.add(
            SandboxRun(
                repository_id=repository_id,
                prompt_version_id=None,
                query="dashboard",
                model="local",
                retrieval_settings={},
                prompt_snapshot={},
                answer="answer",
                latency_ms=1,
                status="complete",
            )
        )
        session.add(
            SandboxComparison(
                repository_id=repository_id,
                query="dashboard",
                status="complete",
                expected_run_count=1,
            )
        )
        session.add(
            RepositorySnapshot(
                repository_id=repository_id,
                manifest={"repository": {"id": repository_id}, "kind": "export"},
            )
        )
        session.add(
            RepositorySnapshot(
                repository_id=other_repository.id,
                manifest={"repository": {"id": other_repository.id}, "kind": "export"},
            )
        )
        session.commit()

    response = client.get(f"/repositories/{repository_id}/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"]["documents"] == 1
    assert payload["counts"]["parsed_documents"] == 1
    assert payload["counts"]["chunks"] == 2
    assert payload["counts"]["chat_sessions"] == 1
    assert payload["counts"]["chat_messages"] == 1
    assert payload["counts"]["retrieval_runs"] == 1
    assert payload["counts"]["sandbox_runs"] == 1
    assert payload["counts"]["sandbox_comparisons"] == 1
    assert payload["full_text"]["status"] == "ready"
    assert payload["vector"]["status"] == "ready"
    assert payload["vector"]["model"] == "test-deterministic"
    activity = payload["recent_activity"]
    activity_kinds = {item["kind"] for item in activity}
    activity_labels = {item["label"] for item in activity}
    assert {"document", "chat", "retrieval", "sandbox", "export", "recreate"} <= activity_kinds
    assert "dashboard.txt" in activity_labels
    assert "Dashboard chat" in activity_labels
    assert "dashboard" in activity_labels
    assert "Repository manifest" in activity_labels
    assert "other.txt" not in activity_labels
    assert "Other chat" not in activity_labels
    assert [item["occurred_at"] for item in activity] == sorted(
        (item["occurred_at"] for item in activity),
        reverse=True,
    )


def test_repository_admin_inventory_lists_scoped_counts_and_index_status() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    test_app = cast(Any, client.app)
    with test_app.state.test_session_factory() as session:
        other_repository = Repository(name="Other Repository", root_path="/tmp/other")
        session.add(other_repository)
        session.flush()
        other_repository.settings = repository_models.RepositorySettingsRow(
            settings=created["settings"]
        )
        _add_document_with_chunks(session, repository_id, "admin.txt", 2)
        _add_document_with_chunks(session, other_repository.id, "other-admin.txt", 1)
        chat_session = ChatSession(
            repository_id=repository_id,
            title="Admin chat",
            model="local",
            retrieval_settings={},
            prompt_id="rag-chat-default-v1",
        )
        session.add(chat_session)
        session.flush()
        session.add(
            ChatMessageRow(
                session_id=chat_session.id,
                repository_id=repository_id,
                sequence=1,
                role="user",
                content="inventory",
            )
        )
        session.add(
            RetrievalRun(
                repository_id=repository_id,
                mode="hybrid",
                query="inventory",
                filters={},
                top_k=5,
                candidate_pool_size=25,
                rrf_constant=60,
                reranker_strategy="none",
                metadata_boosts={},
                settings_snapshot={},
            )
        )
        session.add(
            SandboxRun(
                repository_id=repository_id,
                prompt_version_id=None,
                query="inventory",
                model="local",
                retrieval_settings={},
                prompt_snapshot={},
                answer="answer",
                latency_ms=1,
                status="complete",
            )
        )
        session.add(RepositorySnapshot(repository_id=repository_id, manifest={"kind": "export"}))
        session.commit()
        rebuild_full_text_index(session, repository_id)
        session.add(
            EmbeddingRun(
                repository_id=repository_id,
                provider="sentence_transformers",
                model="test-deterministic",
                vector_size=8,
                distance="cosine",
                collection_name="default_repository",
                status="indexed",
                chunk_count=2,
                settings_snapshot={},
            )
        )
        session.commit()

    response = client.get("/repositories/admin/inventory")

    assert response.status_code == 200
    payload = response.json()
    summaries = {item["repository"]["name"]: item for item in payload["repositories"]}
    assert {"Default Repository", "Other Repository"} <= summaries.keys()
    default = summaries["Default Repository"]
    other = summaries["Other Repository"]
    assert default["counts"]["documents"] == 1
    assert default["counts"]["chunks"] == 2
    assert default["counts"]["chat_sessions"] == 1
    assert default["counts"]["chat_messages"] == 1
    assert default["counts"]["retrieval_runs"] == 1
    assert default["counts"]["sandbox_runs"] == 1
    assert default["counts"]["exports"] == 1
    assert default["full_text"]["status"] == "ready"
    assert default["vector"]["status"] == "ready"
    assert other["counts"]["documents"] == 1
    assert other["counts"]["chunks"] == 1
    assert other["counts"]["chat_sessions"] == 0
    assert other["full_text"]["status"] == "missing"
    hint_categories = {hint["category"] for hint in default["storage_hints"]}
    assert {
        "database_records",
        "app_managed_sources",
        "external_sources",
        "full_text_index",
        "vector_index",
        "exports",
        "prompt_sandbox_history",
        "chat_retrieval_history",
        "model_caches",
    } <= hint_categories
    assert any(
        hint["category"] == "model_caches" and hint["status"] == "out_of_scope"
        for hint in default["storage_hints"]
    )
    assert any(
        hint["category"] == "external_sources" and hint["status"] == "preserved"
        for hint in default["storage_hints"]
    )


def test_repository_delete_preview_reports_cleanup_plan_without_mutating() -> None:
    client = _client_with_database()
    _install_readiness_fakes(client)
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    test_app = cast(Any, client.app)
    with test_app.state.test_session_factory() as session:
        _add_document_with_chunks(session, repository_id, "preview.txt", 2)
        session.commit()
        rebuild_full_text_index(session, repository_id)
        session.add(
            EmbeddingRun(
                repository_id=repository_id,
                provider="sentence_transformers",
                model="test-deterministic",
                vector_size=8,
                distance="cosine",
                collection_name="default_repository",
                status="indexed",
                chunk_count=2,
                settings_snapshot={},
            )
        )
        session.add(
            RepositorySnapshot(
                repository_id=repository_id,
                manifest={"repository": {"id": repository_id}, "kind": "export"},
            )
        )
        session.commit()
        before_documents = session.query(Document).filter_by(repository_id=repository_id).count()
        before_chunks = session.query(DocumentChunk).filter_by(repository_id=repository_id).count()

    response = client.get(f"/repositories/{repository_id}/admin/delete-preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["destructive"] is False
    assert payload["repository"]["id"] == repository_id
    assert payload["database_counts"]["documents"] == 1
    assert payload["database_counts"]["document_versions"] == 1
    assert payload["database_counts"]["chunks"] == 2
    assert payload["database_counts"]["settings"] == 1
    assert payload["database_counts"]["embedding_runs"] == 1
    assert payload["database_counts"]["snapshots"] == 1
    plan = {item["category"]: item for item in payload["plan"]}
    assert plan["database_records"]["action"] == "remove"
    assert plan["full_text_index"]["count"] == 2
    assert plan["vector_index"]["action"] == "retry_required"
    assert plan["external_sources"]["action"] == "preserve"
    assert plan["model_caches"]["action"] == "preserve"
    assert payload["warnings"][0]["code"] == "qdrant_unavailable"
    assert payload["warnings"][0]["retryable"] is True

    with test_app.state.test_session_factory() as session:
        after_documents = session.query(Document).filter_by(repository_id=repository_id).count()
        after_chunks = session.query(DocumentChunk).filter_by(repository_id=repository_id).count()
    assert after_documents == before_documents
    assert after_chunks == before_chunks


def test_repository_delete_requires_confirmation_and_cleans_one_repository(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setenv("PRIVATE_RAG_DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    client = _client_with_database()
    _install_readiness_fakes(client)
    app = cast(Any, client.app)
    app.dependency_overrides[get_admin_vector_store] = lambda: FailingDeleteVectorStore()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    managed_path = data_dir / "repositories" / repository_id / "sources" / "managed.txt"
    derived_dir = data_dir / "repositories" / repository_id / "derived" / "version"
    external_path = tmp_path / "external.txt"
    managed_path.parent.mkdir(parents=True)
    managed_path.write_text("managed")
    derived_dir.mkdir(parents=True)
    (derived_dir / "page.png").write_text("derived")
    external_path.write_text("external")
    with app.state.test_session_factory() as session:
        managed_document = _add_document_with_chunks(session, repository_id, "managed.txt", 1)
        external_document = _add_document_with_chunks(session, repository_id, "external.txt", 1)
        other_repository = Repository(name="Other Repository", root_path=str(tmp_path / "other"))
        session.add(other_repository)
        session.flush()
        other_repository.settings = repository_models.RepositorySettingsRow(
            settings=created["settings"]
        )
        _add_document_with_chunks(session, other_repository.id, "other.txt", 1)
        session.flush()
        session.query(DocumentVersion).filter_by(id=managed_document.current_version_id).update(
            {"storage_path": str(managed_path)}
        )
        session.query(DocumentVersion).filter_by(id=external_document.current_version_id).update(
            {"storage_path": str(external_path)}
        )
        chat_session = ChatSession(
            repository_id=repository_id,
            title="Delete chat",
            model="local",
            retrieval_settings={},
            prompt_id="rag-chat-default-v1",
        )
        session.add(chat_session)
        session.flush()
        session.add(
            ChatMessageRow(
                session_id=chat_session.id,
                repository_id=repository_id,
                sequence=1,
                role="user",
                content="delete",
            )
        )
        session.add(
            RetrievalRun(
                repository_id=repository_id,
                mode="hybrid",
                query="delete",
                filters={},
                top_k=5,
                candidate_pool_size=25,
                rrf_constant=60,
                reranker_strategy="none",
                metadata_boosts={},
                settings_snapshot={},
            )
        )
        session.add(
            SandboxRun(
                repository_id=repository_id,
                prompt_version_id=None,
                query="delete",
                model="local",
                retrieval_settings={},
                prompt_snapshot={},
                answer="answer",
                latency_ms=1,
                status="complete",
            )
        )
        session.add(RepositorySnapshot(repository_id=repository_id, manifest={"kind": "export"}))
        session.commit()
        other_repository_id = other_repository.id
        rebuild_full_text_index(session, repository_id)
        rebuild_full_text_index(session, other_repository_id)
        session.add(
            EmbeddingRun(
                repository_id=repository_id,
                provider="sentence_transformers",
                model="test-deterministic",
                vector_size=8,
                distance="cosine",
                collection_name="default_repository",
                status="indexed",
                chunk_count=2,
                settings_snapshot={},
            )
        )
        session.commit()

    rejected = client.post(
        f"/repositories/{repository_id}/admin/delete",
        json={"confirmation_value": "not the repository name"},
    )

    assert rejected.status_code == 400
    assert managed_path.exists()
    assert external_path.exists()

    response = client.post(
        f"/repositories/{repository_id}/admin/delete",
        json={"confirmation_value": created["repository"]["name"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed_with_warnings"
    removed_categories = {item["category"] for item in payload["removed"]}
    preserved_categories = {item["category"] for item in payload["preserved"]}
    failed_categories = {item["category"] for item in payload["failed"]}
    assert "database_records" in removed_categories
    assert "app_managed_sources" in removed_categories
    assert "full_text_index" in removed_categories
    assert "external_sources" in preserved_categories
    assert "model_caches" in preserved_categories
    assert "vector_index" in failed_categories
    assert any(warning["code"] == "vector_cleanup_incomplete" for warning in payload["warnings"])
    assert not managed_path.exists()
    assert not derived_dir.exists()
    assert external_path.exists()

    with app.state.test_session_factory() as session:
        assert session.get(Repository, repository_id) is None
        assert session.get(Repository, other_repository_id) is not None
        assert session.query(Document).filter_by(repository_id=repository_id).count() == 0
        assert session.query(Document).filter_by(repository_id=other_repository_id).count() == 1
        deleted_fts = session.scalar(
            text("SELECT COUNT(*) FROM full_text_chunks WHERE repository_id = :repository_id"),
            {"repository_id": repository_id},
        )
        other_fts = session.scalar(
            text("SELECT COUNT(*) FROM full_text_chunks WHERE repository_id = :repository_id"),
            {"repository_id": other_repository_id},
        )
        assert deleted_fts == 0
        assert other_fts == 1


def test_clear_all_requires_strong_confirmation_and_recovers_default_repository(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setenv("PRIVATE_RAG_DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    client = _client_with_database()
    _install_readiness_fakes(client)
    app = cast(Any, client.app)
    app.dependency_overrides[get_admin_vector_store] = lambda: FailingDeleteVectorStore()
    created = client.get("/repositories/default").json()
    first_repository_id = created["repository"]["id"]
    first_managed = data_dir / "repositories" / first_repository_id / "sources" / "first.txt"
    first_managed.parent.mkdir(parents=True)
    first_managed.write_text("managed")
    external_path = tmp_path / "external-clear-all.txt"
    external_path.write_text("external")
    with app.state.test_session_factory() as session:
        first_document = _add_document_with_chunks(session, first_repository_id, "first.txt", 1)
        second_repository = Repository(name="Second Repository", root_path=str(data_dir))
        session.add(second_repository)
        session.flush()
        second_repository.settings = repository_models.RepositorySettingsRow(
            settings=created["settings"]
        )
        second_document = _add_document_with_chunks(session, second_repository.id, "second.txt", 1)
        session.flush()
        session.query(DocumentVersion).filter_by(id=first_document.current_version_id).update(
            {"storage_path": str(first_managed)}
        )
        session.query(DocumentVersion).filter_by(id=second_document.current_version_id).update(
            {"storage_path": str(external_path)}
        )
        session.add(
            EmbeddingRun(
                repository_id=first_repository_id,
                provider="sentence_transformers",
                model="test-deterministic",
                vector_size=8,
                distance="cosine",
                collection_name="first_collection",
                status="indexed",
                chunk_count=1,
                settings_snapshot={},
            )
        )
        session.add(
            EmbeddingRun(
                repository_id=second_repository.id,
                provider="sentence_transformers",
                model="test-deterministic",
                vector_size=8,
                distance="cosine",
                collection_name="second_collection",
                status="indexed",
                chunk_count=1,
                settings_snapshot={},
            )
        )
        session.commit()
        second_repository_id = second_repository.id
        rebuild_full_text_index(session, first_repository_id)
        rebuild_full_text_index(session, second_repository_id)

    preview = client.get("/repositories/admin/clear-all/preview")

    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["destructive"] is False
    assert preview_payload["confirmation_value"] == "DELETE ALL LOCAL REPOSITORIES"
    assert len(preview_payload["repositories"]) == 2
    assert preview_payload["database_counts"]["repositories"] == 2
    assert preview_payload["database_counts"]["documents"] == 2
    assert preview_payload["database_counts"]["chunks"] == 2
    assert {item["category"] for item in preview_payload["plan"]} >= {
        "database_records",
        "app_managed_sources",
        "external_sources",
        "full_text_index",
        "vector_index",
        "model_caches",
    }

    rejected = client.post(
        "/repositories/admin/clear-all",
        json={"confirmation_value": "Default Repository"},
    )

    assert rejected.status_code == 400
    assert first_managed.exists()

    response = client.post(
        "/repositories/admin/clear-all",
        json={"confirmation_value": "DELETE ALL LOCAL REPOSITORIES"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed_with_warnings"
    assert payload["database_counts"]["repositories"] == 2
    assert payload["default_repository"]["repository"]["name"] == "Default Repository"
    assert {item["category"] for item in payload["removed"]} >= {
        "database_records",
        "app_managed_sources",
        "full_text_index",
    }
    assert {item["category"] for item in payload["preserved"]} >= {
        "external_sources",
        "model_caches",
    }
    assert {item["category"] for item in payload["failed"]} == {"vector_index"}
    assert not first_managed.exists()
    assert external_path.exists()

    repositories = client.get("/repositories").json()
    assert len(repositories) == 1
    assert repositories[0]["name"] == "Default Repository"
    assert repositories[0]["id"] not in {first_repository_id, second_repository_id}
    with app.state.test_session_factory() as session:
        assert session.get(Repository, first_repository_id) is None
        assert session.get(Repository, second_repository_id) is None
        deleted_first_fts = session.scalar(
            text("SELECT COUNT(*) FROM full_text_chunks WHERE repository_id = :repository_id"),
            {"repository_id": first_repository_id},
        )
        deleted_second_fts = session.scalar(
            text("SELECT COUNT(*) FROM full_text_chunks WHERE repository_id = :repository_id"),
            {"repository_id": second_repository_id},
        )
        assert deleted_first_fts == 0
        assert deleted_second_fts == 0


def test_repository_summary_reports_partial_and_stale_indexes() -> None:
    client = _client_with_database()
    _install_readiness_fakes(client)
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    test_app = cast(Any, client.app)
    with test_app.state.test_session_factory() as session:
        _add_document_with_chunks(session, repository_id, "partial.txt", 2)
        session.commit()
        rebuild_full_text_index(session, repository_id)
        session.execute(
            text("DELETE FROM full_text_chunks WHERE chunk_index = 1 AND repository_id = :id"),
            {"id": repository_id},
        )
        session.add(
            EmbeddingRun(
                repository_id=repository_id,
                provider="sentence_transformers",
                model="test-deterministic",
                vector_size=8,
                distance="cosine",
                collection_name="default_repository",
                status="indexed",
                chunk_count=1,
                settings_snapshot={},
            )
        )
        session.commit()

    partial_response = client.get(f"/repositories/{repository_id}/summary")

    assert partial_response.status_code == 200
    partial = partial_response.json()
    assert partial["full_text"]["status"] == "partial"
    assert partial["full_text"]["indexed_chunks"] == 1
    assert partial["vector"]["status"] == "partial"
    assert partial["vector"]["indexed_chunks"] == 1

    with test_app.state.test_session_factory() as session:
        session.execute(
            text(
                """
                INSERT INTO full_text_chunks (
                    repository_id, document_id, document_version_id, chunk_id, chunk_index,
                    document_title, section, source_type, document_kind, tags,
                    has_table, has_figure, patent_sections,
                    page_start, page_end, line_start, line_end,
                    title, headings, body, captions, tables, claims, examples
                )
                VALUES (
                    :repository_id, 'stale-doc', 'stale-version', 'stale-chunk', 99,
                    'stale.txt', NULL, 'upload', '', '',
                    '0', '0', '',
                    NULL, NULL, NULL, NULL,
                    '', '', 'stale', '', '', '', ''
                ),
                (
                    :repository_id, 'stale-doc-2', 'stale-version-2', 'stale-chunk-2', 100,
                    'stale-2.txt', NULL, 'upload', '', '',
                    '0', '0', '',
                    NULL, NULL, NULL, NULL,
                    '', '', 'stale again', '', '', '', ''
                )
                """
            ),
            {"repository_id": repository_id},
        )
        session.query(EmbeddingRun).filter_by(repository_id=repository_id).update(
            {"chunk_count": 3}
        )
        session.commit()

    stale_response = client.get(f"/repositories/{repository_id}/summary")

    assert stale_response.status_code == 200
    stale = stale_response.json()
    assert stale["full_text"]["status"] == "stale"
    assert "rebuild recommended" in stale["full_text"]["message"]
    assert stale["vector"]["status"] == "stale"
    assert "rebuild recommended" in stale["vector"]["message"]


def test_repository_summary_returns_404_for_missing_repository() -> None:
    client = _client_with_database()
    _install_readiness_fakes(client)

    response = client.get("/repositories/missing/summary")

    assert response.status_code == 404


def test_recreate_validation_endpoint_reports_clear_issues(tmp_path: Path) -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    manifest = client.get(f"/repositories/{created['repository']['id']}/manifest").json()
    manifest["source_files"] = [str(tmp_path / "missing.pdf")]

    response = client.post(
        "/repositories/recreate/validate",
        json={"manifest": manifest, "available_models": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_recreate"] is False
    assert payload["missing_source_files"][0]["code"] == "missing_source_file"


def _install_readiness_fakes(client: TestClient) -> None:
    app = cast(Any, client.app)
    app.dependency_overrides[get_settings_chat_llm] = lambda: FakeSettingsLLM()
    app.dependency_overrides[get_settings_readiness_checker] = lambda: (
        FakeSettingsReadinessChecker()
    )


def _add_document_with_chunks(
    session: Session,
    repository_id: str,
    display_name: str,
    chunk_count: int,
) -> Document:
    document = Document(repository_id=repository_id, display_name=display_name)
    session.add(document)
    session.flush()
    version = DocumentVersion(
        document_id=document.id,
        repository_id=repository_id,
        original_filename=display_name,
        content_type="text/plain",
        source_type="upload",
        sha256="0" * 64,
        byte_size=100,
        storage_path=f"/tmp/{display_name}",
        status="parsed",
        parser_name="test",
        parser_version="1",
        chunk_count=chunk_count,
    )
    session.add(version)
    session.flush()
    document.current_version_id = version.id
    for index in range(chunk_count):
        session.add(
            DocumentChunk(
                repository_id=repository_id,
                document_id=document.id,
                document_version_id=version.id,
                chunk_index=index,
                text=f"{display_name} chunk {index}",
                parser_version="1",
            )
        )
    return document
