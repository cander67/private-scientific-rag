from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.chat.llm import ChatLLM
from private_rag.chat.models import ChatMessageRow, ChatSession
from private_rag.core.settings import Settings
from private_rag.db.base import Base
from private_rag.ingestion.models import Document, DocumentChunk, DocumentVersion
from private_rag.prompt_sandbox.models import SandboxPromptVersion, SandboxRun
from private_rag.repositories import models as repository_models  # noqa: F401
from private_rag.repositories.models import Repository, RepositorySettingsRow, RepositorySnapshot
from private_rag.repositories.schemas import RepositorySettings, RepositorySettingsReadinessItem
from private_rag.repositories.service import (
    delete_repository_with_cleanup,
    preview_repository_deletion,
)
from private_rag.retrieval.models import RetrievalResult, RetrievalRun
from private_rag.vector.models import EmbeddingRun
from private_rag.vector.store import InMemoryVectorStore


class FakeCleanupChecker:
    def __init__(self, *, qdrant_ready: bool) -> None:
        self.qdrant_ready = qdrant_ready

    def check_qdrant(
        self, *, qdrant_url: str, collection_name: str
    ) -> RepositorySettingsReadinessItem:
        if self.qdrant_ready:
            return RepositorySettingsReadinessItem(
                target="qdrant",
                label="Qdrant",
                status="ready",
                ready=True,
                message=f"{collection_name} is reachable.",
                model=collection_name,
            )
        return RepositorySettingsReadinessItem(
            target="qdrant",
            label="Qdrant",
            status="unavailable_runtime",
            ready=False,
            message="Qdrant is unavailable in this test runtime.",
            model=collection_name,
        )

    def check_chat(self, *, llm: ChatLLM, model: str) -> RepositorySettingsReadinessItem:
        return RepositorySettingsReadinessItem(
            target="chat",
            label="Chat model",
            status="skipped",
            ready=False,
            message="Chat readiness is not used by cleanup preview tests.",
            model=model,
        )

    def check_embedding(
        self,
        *,
        provider: str,
        model: str,
        expected_vector_size: int,
        ollama_base_url: str,
    ) -> RepositorySettingsReadinessItem:
        return RepositorySettingsReadinessItem(
            target="embedding",
            label="Embedding model",
            status="skipped",
            ready=False,
            message="Embedding readiness is not used by cleanup preview tests.",
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
            message="Reranker readiness is not used by cleanup preview tests.",
            model=model,
        )


def test_delete_preview_classifies_storage_and_warns_without_mutating(tmp_path: Path) -> None:
    session_factory = _session_factory()
    settings = Settings(data_dir=tmp_path / "data")
    app_managed_path = settings.data_dir / "repositories" / "repo-1" / "sources" / "managed.txt"
    external_path = tmp_path / "external" / "source.txt"
    with session_factory() as session:
        repository = Repository(
            id="repo-1", name="Preview Repository", root_path=str(settings.data_dir)
        )
        session.add(repository)
        session.flush()
        repository.settings = RepositorySettingsRow(
            settings=RepositorySettings.from_app_settings(settings).model_dump(mode="json")
        )
        _add_version(session, repository.id, "managed", app_managed_path)
        _add_version(session, repository.id, "external", external_path)
        chat_session = ChatSession(
            repository_id=repository.id,
            title="Preview chat",
            model="local",
            retrieval_settings={},
            prompt_id="rag-chat-default-v1",
        )
        session.add(chat_session)
        session.flush()
        session.add(
            ChatMessageRow(
                session_id=chat_session.id,
                repository_id=repository.id,
                sequence=1,
                role="user",
                content="preview",
            )
        )
        retrieval_run = RetrievalRun(
            repository_id=repository.id,
            mode="hybrid",
            query="preview",
            filters={},
            top_k=5,
            candidate_pool_size=25,
            rrf_constant=60,
            reranker_strategy="none",
            metadata_boosts={},
            settings_snapshot={},
        )
        session.add(retrieval_run)
        session.flush()
        session.add(
            RetrievalResult(
                run_id=retrieval_run.id,
                repository_id=repository.id,
                document_id="doc",
                document_version_id="version",
                chunk_id="chunk",
                chunk_index=0,
                rank=1,
                final_score=1.0,
                score_breakdown={},
                source_ranks={},
                matched_fields=[],
                result_metadata={},
            )
        )
        sandbox_prompt = SandboxPromptVersion(
            repository_id=repository.id,
            name="Prompt",
            body="Body",
        )
        session.add(sandbox_prompt)
        session.flush()
        session.add(
            SandboxRun(
                repository_id=repository.id,
                prompt_version_id=sandbox_prompt.id,
                query="preview",
                model="local",
                retrieval_settings={},
                prompt_snapshot={},
                answer="answer",
                latency_ms=1,
                status="complete",
            )
        )
        session.add(
            EmbeddingRun(
                repository_id=repository.id,
                provider="sentence_transformers",
                model="test",
                vector_size=8,
                distance="cosine",
                collection_name="preview_collection",
                status="indexed",
                chunk_count=2,
                settings_snapshot={},
            )
        )
        session.add(RepositorySnapshot(repository_id=repository.id, manifest={"kind": "export"}))
        session.commit()

        preview = preview_repository_deletion(
            session,
            repository_id=repository.id,
            app_settings=settings,
            checker=FakeCleanupChecker(qdrant_ready=False),
        )

        assert preview is not None
        assert preview.destructive is False
        assert preview.database_counts.documents == 2
        assert preview.database_counts.document_versions == 2
        assert preview.database_counts.chunks == 2
        assert preview.database_counts.chat_sessions == 1
        assert preview.database_counts.chat_messages == 1
        assert preview.database_counts.retrieval_runs == 1
        assert preview.database_counts.retrieval_results == 1
        assert preview.database_counts.sandbox_prompts == 1
        assert preview.database_counts.sandbox_runs == 1
        assert preview.database_counts.embedding_runs == 1
        assert preview.database_counts.snapshots == 1
        items = {item.category: item for item in preview.plan}
        assert str(app_managed_path) in items["app_managed_sources"].paths
        assert str(external_path) in items["external_sources"].paths
        assert items["external_sources"].action == "preserve"
        assert items["model_caches"].action == "preserve"
        assert items["vector_index"].action == "retry_required"
        assert preview.warnings[0].code == "qdrant_unavailable"
        assert session.get(Repository, repository.id) is not None
        assert session.query(Document).filter_by(repository_id=repository.id).count() == 2


def test_confirmed_delete_removes_managed_files_and_preserves_external_sources(
    tmp_path: Path,
) -> None:
    session_factory = _session_factory()
    settings = Settings(data_dir=tmp_path / "data")
    app_managed_path = settings.data_dir / "repositories" / "repo-1" / "sources" / "managed.txt"
    derived_path = settings.data_dir / "repositories" / "repo-1" / "derived" / "version"
    external_path = tmp_path / "external" / "source.txt"
    app_managed_path.parent.mkdir(parents=True)
    app_managed_path.write_text("managed")
    derived_path.mkdir(parents=True)
    (derived_path / "page.png").write_text("derived")
    external_path.parent.mkdir(parents=True)
    external_path.write_text("external")
    vector_store = InMemoryVectorStore()
    vector_store.recreate_collection("preview_collection", 8, "cosine")

    with session_factory() as session:
        repository = Repository(
            id="repo-1", name="Preview Repository", root_path=str(settings.data_dir)
        )
        session.add(repository)
        session.flush()
        repository.settings = RepositorySettingsRow(
            settings=RepositorySettings.from_app_settings(settings).model_dump(mode="json")
        )
        _add_version(session, repository.id, "managed", app_managed_path)
        _add_version(session, repository.id, "external", external_path)
        session.add(
            EmbeddingRun(
                repository_id=repository.id,
                provider="sentence_transformers",
                model="test",
                vector_size=8,
                distance="cosine",
                collection_name="preview_collection",
                status="indexed",
                chunk_count=2,
                settings_snapshot={},
            )
        )
        session.commit()
        repository_id = repository.id
        repository_name = repository.name

        result = delete_repository_with_cleanup(
            session,
            repository_id=repository_id,
            confirmation_value=repository_name,
            app_settings=settings,
            checker=FakeCleanupChecker(qdrant_ready=True),
            vector_store=vector_store,
        )

        assert result is not None
        assert result.status == "completed"
        assert session.get(Repository, repository_id) is None
        assert session.query(Document).filter_by(repository_id=repository_id).count() == 0
        assert not app_managed_path.exists()
        assert not derived_path.exists()
        assert external_path.exists()
        assert "preview_collection" not in vector_store.collections
        removed_categories = {item.category for item in result.removed}
        preserved_categories = {item.category for item in result.preserved}
        assert "database_records" in removed_categories
        assert "app_managed_sources" in removed_categories
        assert "vector_index" in removed_categories
        assert "external_sources" in preserved_categories
        assert "model_caches" in preserved_categories


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def _add_version(session: Session, repository_id: str, name: str, path: Path) -> None:
    document = Document(repository_id=repository_id, display_name=f"{name}.txt")
    session.add(document)
    session.flush()
    version = DocumentVersion(
        document_id=document.id,
        repository_id=repository_id,
        original_filename=f"{name}.txt",
        content_type="text/plain",
        source_type="text",
        sha256=name.rjust(64, "0")[-64:],
        byte_size=10,
        storage_path=str(path),
        status="parsed",
        parser_name="test",
        parser_version="1",
        chunk_count=1,
    )
    session.add(version)
    session.flush()
    document.current_version_id = version.id
    session.add(
        DocumentChunk(
            repository_id=repository_id,
            document_id=document.id,
            document_version_id=version.id,
            chunk_index=0,
            text=f"{name} text",
            parser_version="1",
        )
    )
