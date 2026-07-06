from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from private_rag.search.schemas import FullTextSearchFilters
from private_rag.search.service import rebuild_full_text_index, search_full_text


class ExactMatchQuery(BaseModel):
    id: str
    query: str
    expected_document_title: str


class RecallMetric(BaseModel):
    k: int
    retrieved: int
    total: int
    recall: float


class ExactMatchEvaluationResult(BaseModel):
    repository_id: str
    indexed_chunks: int
    metrics: list[RecallMetric] = Field(default_factory=list)


def evaluate_exact_match_recall(
    session: Session,
    repository_id: str,
    queries: list[ExactMatchQuery],
    k_values: tuple[int, ...] = (5, 10),
) -> ExactMatchEvaluationResult | None:
    rebuilt = rebuild_full_text_index(session, repository_id)
    if rebuilt is None:
        return None

    hits = {k: 0 for k in k_values}
    for query in queries:
        response = search_full_text(
            session=session,
            repository_id=repository_id,
            query=query.query,
            limit=max(k_values),
            filters=FullTextSearchFilters(),
        )
        if response is None:
            return None
        titles = [result.document_title for result in response.results]
        for k in k_values:
            if query.expected_document_title in titles[:k]:
                hits[k] += 1

    total = len(queries)
    metrics = [
        RecallMetric(
            k=k,
            retrieved=hits[k],
            total=total,
            recall=hits[k] / total if total else 0.0,
        )
        for k in k_values
    ]
    return ExactMatchEvaluationResult(
        repository_id=repository_id,
        indexed_chunks=rebuilt.indexed_chunks,
        metrics=metrics,
    )
