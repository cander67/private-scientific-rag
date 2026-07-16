from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.db.base import Base
from private_rag.ingestion.models import DocumentChunk
from private_rag.ingestion.service import upload_document
from private_rag.repositories.service import ensure_default_repository, update_repository_settings
from private_rag.vector.embeddings import DeterministicEmbeddingProvider
from private_rag.vector.evaluation import (
    EmbeddingModelEvaluationSpec,
    SemanticQuery,
    compare_embedding_model_recall,
    evaluate_semantic_recall,
    known_embedding_evaluation_specs,
)
from private_rag.vector.service import rebuild_vector_index
from private_rag.vector.store import InMemoryVectorStore


class _EvaluationEmbeddingFactory:
    def __init__(self, *, unavailable_models: set[str] | None = None) -> None:
        self.unavailable_models = unavailable_models or set()
        self.created: list[tuple[str, str]] = []

    def create(self, *, provider: str, model: str) -> DeterministicEmbeddingProvider:
        self.created.append((provider, model))
        if model in self.unavailable_models:
            if provider == "ollama":
                raise RuntimeError(f"Start Ollama and run `ollama pull {model}`.")
            raise RuntimeError(
                f"Cache or install embedding model '{model}' before live evaluation."
            )
        vector_sizes = {
            "sentence-transformers/all-MiniLM-L6-v2": 384,
            "sentence-transformers/all-mpnet-base-v2": 768,
            "embeddinggemma:300m": 768,
            "qwen3-embedding:8b": 4096,
        }
        return DeterministicEmbeddingProvider(
            model_name=model,
            vector_size=vector_sizes.get(model, 8),
        )


def test_semantic_recall_evaluation_records_fixture_recall() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    store = InMemoryVectorStore()
    embedder = DeterministicEmbeddingProvider(vector_size=8)

    with session_factory() as session:
        repository = ensure_default_repository(session)
        settings = repository.settings.model_copy(deep=True)
        settings.embedding.model = "test-deterministic"
        settings.vector.vector_size = 8
        updated = update_repository_settings(session, repository.repository.id, settings)
        assert updated is not None
        uploaded = upload_document(
            session=session,
            repository_id=repository.repository.id,
            filename="semantic-fixture.txt",
            content_type="text/plain",
            data=(
                b"Abstract\n"
                b"Lithium iron phosphate cathodes retain capacity during cycling.\n"
                b"Methods\n"
                b"UV curable epoxy acrylate binders improve adhesive strength.\n"
            ),
        )
        assert uploaded is not None
        rebuilt = rebuild_vector_index(session, repository.repository.id, store, embedder)
        assert rebuilt is not None

        fixture_path = (
            Path(__file__).parents[1] / "fixtures" / "search" / "prd5_semantic_fixture.json"
        )
        fixture = json.loads(fixture_path.read_text())
        chunks = session.execute(select(DocumentChunk)).scalars()
        expected_by_term = {
            term: chunk.id
            for chunk in chunks
            for query in fixture["queries"]
            for term in query["expected_terms"]
            if term in chunk.text
        }
        queries = [
            SemanticQuery(
                query=query["query"],
                expected_chunk_ids=[expected_by_term[query["expected_terms"][0]]],
            )
            for query in fixture["queries"]
        ]

        result = evaluate_semantic_recall(
            session,
            repository.repository.id,
            queries,
            store,
            embedder,
            k_values=(1, 5),
        )

    assert result.query_count == 2
    assert result.recall_at[5] == 1.0


def test_embedding_model_comparison_records_per_model_recall_and_metadata() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    store = InMemoryVectorStore()
    embedder = _EvaluationEmbeddingFactory()

    with session_factory() as session:
        repository = ensure_default_repository(session)
        settings = repository.settings.model_copy(deep=True)
        settings.embedding.model = "test-deterministic"
        settings.vector.vector_size = 8
        updated = update_repository_settings(session, repository.repository.id, settings)
        assert updated is not None
        queries = _seed_semantic_fixture(session, repository.repository.id)

        result = compare_embedding_model_recall(
            session=session,
            repository_id=repository.repository.id,
            queries=queries,
            store=store,
            embedder=embedder,
            specs=known_embedding_evaluation_specs(fixture_name="prd5_semantic_fixture"),
            fixture_name="prd5_semantic_fixture",
            k_values=(1, 5),
        )

    rows = {(row.provider, row.model): row for row in result.results}
    assert result.fixture_name == "prd5_semantic_fixture"
    assert set(rows) == {
        ("sentence_transformers", "sentence-transformers/all-MiniLM-L6-v2"),
        ("sentence_transformers", "sentence-transformers/all-mpnet-base-v2"),
        ("ollama", "embeddinggemma:300m"),
        ("ollama", "qwen3-embedding:8b"),
    }
    assert (
        rows[("sentence_transformers", "sentence-transformers/all-MiniLM-L6-v2")].vector_size == 384
    )
    assert (
        rows[("sentence_transformers", "sentence-transformers/all-mpnet-base-v2")].vector_size
        == 768
    )
    assert rows[("ollama", "embeddinggemma:300m")].vector_size == 768
    assert rows[("ollama", "qwen3-embedding:8b")].vector_size == 4096
    assert all(row.status == "completed" for row in rows.values())
    assert all(row.fixture_name == "prd5_semantic_fixture" for row in rows.values())
    assert all(row.distance == "cosine" for row in rows.values())
    assert all(row.query_count == 2 for row in rows.values())
    assert all(row.recall_at[5] == 1.0 for row in rows.values())


def test_embedding_model_comparison_reports_skips_and_restores_settings() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    store = InMemoryVectorStore()
    embedder = _EvaluationEmbeddingFactory(unavailable_models={"embeddinggemma:300m"})

    with session_factory() as session:
        repository = ensure_default_repository(session)
        settings = repository.settings.model_copy(deep=True)
        settings.embedding.model = "test-deterministic"
        settings.vector.vector_size = 8
        updated = update_repository_settings(session, repository.repository.id, settings)
        assert updated is not None
        queries = _seed_semantic_fixture(session, repository.repository.id)

        result = compare_embedding_model_recall(
            session=session,
            repository_id=repository.repository.id,
            queries=queries,
            store=store,
            embedder=embedder,
            specs=[
                EmbeddingModelEvaluationSpec(
                    provider="sentence_transformers",
                    model="sentence-transformers/all-MiniLM-L6-v2",
                    vector_size=384,
                    fixture_name="prd5_semantic_fixture",
                ),
                EmbeddingModelEvaluationSpec(
                    provider="ollama",
                    model="embeddinggemma:300m",
                    vector_size=768,
                    fixture_name="prd5_semantic_fixture",
                ),
            ],
            fixture_name="prd5_semantic_fixture",
            k_values=(5,),
        )
        restored = ensure_default_repository(session).settings

    completed, skipped = result.results
    assert completed.status == "completed"
    assert completed.recall_at[5] == 1.0
    assert skipped.status == "skipped"
    assert skipped.model == "embeddinggemma:300m"
    assert skipped.skipped_reason == "Start Ollama and run `ollama pull embeddinggemma:300m`."
    assert skipped.recall_at == {}
    assert restored.embedding.model == "test-deterministic"
    assert restored.vector.vector_size == 8


def _seed_semantic_fixture(session: Session, repository_id: str) -> list[SemanticQuery]:
    uploaded = upload_document(
        session=session,
        repository_id=repository_id,
        filename="semantic-fixture.txt",
        content_type="text/plain",
        data=(
            b"Abstract\n"
            b"Lithium iron phosphate cathodes retain capacity during cycling.\n"
            b"Methods\n"
            b"UV curable epoxy acrylate binders improve adhesive strength.\n"
        ),
    )
    assert uploaded is not None
    fixture_path = Path(__file__).parents[1] / "fixtures" / "search" / "prd5_semantic_fixture.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    chunks = session.execute(select(DocumentChunk)).scalars()
    expected_by_term = {
        term: chunk.id
        for chunk in chunks
        for query in fixture["queries"]
        for term in query["expected_terms"]
        if term in chunk.text
    }
    return [
        SemanticQuery(
            query=query["query"],
            expected_chunk_ids=[expected_by_term[query["expected_terms"][0]]],
        )
        for query in fixture["queries"]
    ]
