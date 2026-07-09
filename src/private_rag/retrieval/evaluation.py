from __future__ import annotations

from typing import cast

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from private_rag.retrieval.rerankers import RerankerProvider
from private_rag.retrieval.schemas import (
    MetadataBoostSettings,
    RerankerStrategy,
    RetrievalMode,
    RetrievalSearchRequest,
)
from private_rag.retrieval.service import search_retrieval
from private_rag.search.schemas import FullTextSearchFilters
from private_rag.vector.embeddings import EmbeddingProvider
from private_rag.vector.store import VectorStore


class RetrievalEvaluationQuery(BaseModel):
    query: str
    expected_terms: list[str] = Field(min_length=1)


class RetrievalModeMetric(BaseModel):
    mode: RetrievalMode
    reranker_strategy: str
    recall_at: dict[int, float]


class RetrievalComparisonResult(BaseModel):
    repository_id: str
    query_count: int
    metrics: list[RetrievalModeMetric]


def evaluate_retrieval_comparison(
    session: Session,
    repository_id: str,
    queries: list[RetrievalEvaluationQuery],
    store: VectorStore,
    embedder: EmbeddingProvider,
    reranker: RerankerProvider,
    k_values: tuple[int, ...] = (1, 5),
) -> RetrievalComparisonResult:
    mode_requests: list[tuple[RetrievalMode, RerankerStrategy]] = [
        ("full_text", "none"),
        ("vector", "none"),
        ("hybrid", "none"),
        ("hybrid", "cross_encoder"),
        ("hybrid", "metadata_boost"),
        ("hybrid", "cross_encoder_metadata_boost"),
    ]
    metrics = [
        _evaluate_mode(
            session=session,
            repository_id=repository_id,
            queries=queries,
            mode=mode,
            reranker_strategy=reranker_strategy,
            store=store,
            embedder=embedder,
            reranker=reranker,
            k_values=k_values,
        )
        for mode, reranker_strategy in mode_requests
    ]
    return RetrievalComparisonResult(
        repository_id=repository_id,
        query_count=len(queries),
        metrics=metrics,
    )


def _evaluate_mode(
    *,
    session: Session,
    repository_id: str,
    queries: list[RetrievalEvaluationQuery],
    mode: RetrievalMode,
    reranker_strategy: RerankerStrategy,
    store: VectorStore,
    embedder: EmbeddingProvider,
    reranker: RerankerProvider,
    k_values: tuple[int, ...],
) -> RetrievalModeMetric:
    hits_by_k = {k: 0 for k in k_values}
    max_k = max(k_values)
    for query in queries:
        response = search_retrieval(
            session=session,
            repository_id=repository_id,
            request=RetrievalSearchRequest(
                query=query.query,
                mode=mode,
                top_k=max_k,
                candidate_pool_size=max_k * 5,
                reranker_strategy=reranker_strategy,
                metadata_boosts=MetadataBoostSettings(
                    section="high",
                    patent_section="high",
                    document_kind="high",
                    table_figure="medium",
                ),
                filters=FullTextSearchFilters(),
            ),
            store=store,
            embedder=embedder,
            reranker=reranker,
        )
        if response is None:
            continue
        result_texts = [
            " ".join(
                value
                for value in [
                    result.document_title,
                    result.snippet or "",
                    result.text_preview or "",
                    result.section or "",
                ]
                if value
            )
            for result in response.results
        ]
        for k in k_values:
            if _has_expected_term(result_texts[:k], query.expected_terms):
                hits_by_k[k] += 1

    query_count = len(queries)
    return RetrievalModeMetric(
        mode=mode,
        reranker_strategy=cast(str, reranker_strategy),
        recall_at={k: hits / query_count if query_count else 0.0 for k, hits in hits_by_k.items()},
    )


def _has_expected_term(result_texts: list[str], expected_terms: list[str]) -> bool:
    haystack = "\n".join(result_texts).lower()
    return any(term.lower() in haystack for term in expected_terms)
