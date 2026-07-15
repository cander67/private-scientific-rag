from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.core.settings import Settings
from private_rag.db.base import Base
from private_rag.ingestion.service import upload_document
from private_rag.repositories.service import ensure_default_repository, update_repository_settings
from private_rag.vector.embeddings import SentenceTransformersEmbeddingProvider
from private_rag.vector.schemas import VectorSearchFilters
from private_rag.vector.service import (
    collection_name_for_repository,
    rebuild_vector_index,
    search_vector_index,
)
from private_rag.vector.store import QdrantVectorStore


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1")
def test_live_vector_search_with_qdrant_and_sentence_transformers(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    store = QdrantVectorStore(settings.qdrant_url)
    embedder = SentenceTransformersEmbeddingProvider(settings.default_embedding_model, device="cpu")
    repository_id: str | None = None
    response = None

    try:
        with session_factory() as session:
            repository = ensure_default_repository(session, settings)
            repository_id = repository.repository.id
            repository_settings = repository.settings.model_copy(deep=True)
            repository_settings.vector.vector_size = embedder.vector_size
            update_repository_settings(session, repository_id, repository_settings)
            uploaded = upload_document(
                session=session,
                repository_id=repository_id,
                filename="live-vector-smoke.txt",
                content_type="text/plain",
                data=(
                    b"Abstract\n"
                    b"Lithium iron phosphate cathodes retain capacity during battery cycling.\n"
                ),
                settings=settings,
            )
            assert uploaded is not None
            rebuilt = rebuild_vector_index(session, repository_id, store, embedder)
            assert rebuilt is not None
            response = search_vector_index(
                session=session,
                repository_id=repository_id,
                query="lithium phosphate battery cathode",
                limit=3,
                filters=VectorSearchFilters(),
                store=store,
                embedder=embedder,
            )
    finally:
        if repository_id is not None:
            store.delete_collection(collection_name_for_repository(repository_id))

    assert response is not None
    assert response.results
    assert "Lithium iron phosphate" in response.results[0].text_preview
