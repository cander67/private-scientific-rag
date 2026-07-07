from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from private_rag.vector.embeddings import EmbeddingProvider
from private_rag.vector.schemas import VectorSearchFilters
from private_rag.vector.service import search_vector_index
from private_rag.vector.store import VectorStore


class SemanticQuery(BaseModel):
    query: str
    expected_chunk_ids: list[str] = Field(min_length=1)


class SemanticRecallResult(BaseModel):
    repository_id: str
    recall_at: dict[int, float]
    query_count: int


def evaluate_semantic_recall(
    session: Session,
    repository_id: str,
    queries: list[SemanticQuery],
    store: VectorStore,
    embedder: EmbeddingProvider,
    k_values: tuple[int, ...] = (5, 10),
) -> SemanticRecallResult:
    hits_by_k = {k: 0 for k in k_values}
    max_k = max(k_values)
    for query in queries:
        response = search_vector_index(
            session=session,
            repository_id=repository_id,
            query=query.query,
            limit=max_k,
            filters=VectorSearchFilters(),
            store=store,
            embedder=embedder,
        )
        if response is None:
            continue
        result_ids = [result.chunk_id for result in response.results]
        expected = set(query.expected_chunk_ids)
        for k in k_values:
            if expected.intersection(result_ids[:k]):
                hits_by_k[k] += 1
    query_count = len(queries)
    return SemanticRecallResult(
        repository_id=repository_id,
        recall_at={k: hits / query_count if query_count else 0.0 for k, hits in hits_by_k.items()},
        query_count=query_count,
    )
