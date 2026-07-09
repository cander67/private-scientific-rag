from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.db.base import Base
from private_rag.ingestion.service import upload_document
from private_rag.repositories.service import ensure_default_repository, update_repository_settings
from private_rag.retrieval.evaluation import (
    RetrievalEvaluationQuery,
    evaluate_retrieval_comparison,
)
from private_rag.retrieval.schemas import RetrievalSearchRequest, RetrievalSearchResult
from private_rag.retrieval.service import search_retrieval
from private_rag.search.service import rebuild_full_text_index
from private_rag.vector.embeddings import DeterministicEmbeddingProvider
from private_rag.vector.service import rebuild_vector_index
from private_rag.vector.store import InMemoryVectorStore


class _KeywordReranker:
    def score(
        self,
        query: str,
        results: list[RetrievalSearchResult],
        model_name: str,
    ) -> list[float]:
        query_terms = query.lower().split()
        scores = []
        for result in results:
            text = " ".join(
                value
                for value in [
                    result.document_title,
                    result.snippet or "",
                    result.text_preview or "",
                    result.section or "",
                ]
                if value
            ).lower()
            scores.append(sum(1.0 for term in query_terms if term in text))
        return scores


def test_retrieval_evaluation_compares_modes_and_reranked_hybrid() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    store = InMemoryVectorStore()
    embedder = DeterministicEmbeddingProvider(vector_size=8)
    reranker = _KeywordReranker()
    fixture = _load_fixture()

    with session_factory() as session:
        repository = ensure_default_repository(session)
        settings = repository.settings.model_copy(deep=True)
        settings.embedding.model = "test-deterministic"
        settings.vector.vector_size = 8
        updated = update_repository_settings(session, repository.repository.id, settings)
        assert updated is not None

        for document in fixture["documents"]:
            uploaded = upload_document(
                session=session,
                repository_id=repository.repository.id,
                filename=str(document["filename"]),
                content_type=str(document["content_type"]),
                data=str(document["content"]).encode("utf-8"),
            )
            assert uploaded is not None

        assert rebuild_full_text_index(session, repository.repository.id) is not None
        assert rebuild_vector_index(session, repository.repository.id, store, embedder) is not None

        queries = [RetrievalEvaluationQuery.model_validate(item) for item in fixture["queries"]]
        result = evaluate_retrieval_comparison(
            session=session,
            repository_id=repository.repository.id,
            queries=queries,
            store=store,
            embedder=embedder,
            reranker=reranker,
            k_values=(1, 5),
        )

    metrics = {
        (metric.mode, metric.reranker_strategy): metric.recall_at for metric in result.metrics
    }
    assert result.query_count == 2
    assert set(metrics) == {
        ("full_text", "none"),
        ("vector", "none"),
        ("hybrid", "none"),
        ("hybrid", "cross_encoder"),
        ("hybrid", "metadata_boost"),
        ("hybrid", "cross_encoder_metadata_boost"),
    }
    assert all(recall[5] == 1.0 for recall in metrics.values())
    assert metrics[("hybrid", "cross_encoder")][1] >= metrics[("hybrid", "none")][1]


def test_retrieval_evaluation_reranked_hybrid_records_rerank_scores() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    store = InMemoryVectorStore()
    embedder = DeterministicEmbeddingProvider(vector_size=8)
    reranker = _KeywordReranker()
    fixture = _load_fixture()

    with session_factory() as session:
        repository = ensure_default_repository(session)
        settings = repository.settings.model_copy(deep=True)
        settings.embedding.model = "test-deterministic"
        settings.vector.vector_size = 8
        updated = update_repository_settings(session, repository.repository.id, settings)
        assert updated is not None

        for document in fixture["documents"]:
            uploaded = upload_document(
                session=session,
                repository_id=repository.repository.id,
                filename=str(document["filename"]),
                content_type=str(document["content_type"]),
                data=str(document["content"]).encode("utf-8"),
            )
            assert uploaded is not None

        assert rebuild_full_text_index(session, repository.repository.id) is not None
        assert rebuild_vector_index(session, repository.repository.id, store, embedder) is not None
        query = "epoxy acrylate"
        baseline = search_retrieval(
            session=session,
            repository_id=repository.repository.id,
            request=RetrievalSearchRequest(query=query, mode="hybrid", top_k=2),
            store=store,
            embedder=embedder,
            reranker=reranker,
        )
        reranked = search_retrieval(
            session=session,
            repository_id=repository.repository.id,
            request=RetrievalSearchRequest(
                query=query,
                mode="hybrid",
                top_k=2,
                reranker_strategy="cross_encoder",
            ),
            store=store,
            embedder=embedder,
            reranker=reranker,
        )

    assert reranked is not None
    assert baseline is not None
    assert "rerank" not in baseline.results[0].score_breakdown
    assert "rerank" in reranked.results[0].score_breakdown
    assert reranked.results[0].final_score == reranked.results[0].score_breakdown["rerank"]
    assert (
        "epoxy" in (reranked.results[0].text_preview or reranked.results[0].snippet or "").lower()
    )


def _load_fixture() -> dict[str, list[dict[str, object]]]:
    path = Path(__file__).parents[1] / "fixtures" / "search" / "prd6_retrieval_fixture.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
