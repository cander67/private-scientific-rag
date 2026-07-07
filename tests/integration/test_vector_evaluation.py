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
from private_rag.vector.evaluation import SemanticQuery, evaluate_semantic_recall
from private_rag.vector.service import rebuild_vector_index
from private_rag.vector.store import InMemoryVectorStore


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
