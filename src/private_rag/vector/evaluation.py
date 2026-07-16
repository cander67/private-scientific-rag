from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import RepositorySettings
from private_rag.vector.embeddings import EmbeddingProviderSource
from private_rag.vector.model_registry import EmbeddingModelMetadata, known_embedding_models
from private_rag.vector.schemas import VectorSearchFilters
from private_rag.vector.service import rebuild_vector_index, search_vector_index
from private_rag.vector.store import VectorStore


class SemanticQuery(BaseModel):
    query: str
    expected_chunk_ids: list[str] = Field(min_length=1)


class SemanticRecallResult(BaseModel):
    repository_id: str
    recall_at: dict[int, float]
    query_count: int


class EmbeddingModelEvaluationSpec(BaseModel):
    provider: str
    model: str
    vector_size: int
    distance: str = "cosine"
    fixture_name: str


class EmbeddingModelEvaluationResult(BaseModel):
    provider: str
    model: str
    vector_size: int
    distance: str
    fixture_name: str
    status: str
    recall_at: dict[int, float] = Field(default_factory=dict)
    query_count: int = 0
    skipped_reason: str | None = None


class EmbeddingModelComparisonResult(BaseModel):
    repository_id: str
    fixture_name: str
    results: list[EmbeddingModelEvaluationResult]


def evaluate_semantic_recall(
    session: Session,
    repository_id: str,
    queries: list[SemanticQuery],
    store: VectorStore,
    embedder: EmbeddingProviderSource,
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


def known_embedding_evaluation_specs(
    *,
    fixture_name: str,
) -> list[EmbeddingModelEvaluationSpec]:
    return [_spec_from_metadata(metadata, fixture_name) for metadata in known_embedding_models()]


def compare_embedding_model_recall(
    *,
    session: Session,
    repository_id: str,
    queries: list[SemanticQuery],
    store: VectorStore,
    embedder: EmbeddingProviderSource,
    specs: list[EmbeddingModelEvaluationSpec],
    fixture_name: str,
    k_values: tuple[int, ...] = (5, 10),
) -> EmbeddingModelComparisonResult:
    original_settings = _repository_settings(session, repository_id)
    results: list[EmbeddingModelEvaluationResult] = []
    try:
        for spec in specs:
            try:
                _apply_embedding_settings(session, repository_id, spec)
                rebuilt = rebuild_vector_index(session, repository_id, store, embedder)
                if rebuilt is None:
                    raise RuntimeError("Repository not found while rebuilding vector index.")
                recall = evaluate_semantic_recall(
                    session=session,
                    repository_id=repository_id,
                    queries=queries,
                    store=store,
                    embedder=embedder,
                    k_values=k_values,
                )
            except Exception as exc:
                results.append(_skipped_result(spec, exc))
                continue

            results.append(
                EmbeddingModelEvaluationResult(
                    provider=spec.provider,
                    model=spec.model,
                    vector_size=rebuilt.vector_size,
                    distance=rebuilt.distance,
                    fixture_name=spec.fixture_name,
                    status="completed",
                    recall_at=recall.recall_at,
                    query_count=recall.query_count,
                )
            )
    finally:
        _save_repository_settings(session, repository_id, original_settings)

    return EmbeddingModelComparisonResult(
        repository_id=repository_id,
        fixture_name=fixture_name,
        results=results,
    )


def _spec_from_metadata(
    metadata: EmbeddingModelMetadata,
    fixture_name: str,
) -> EmbeddingModelEvaluationSpec:
    return EmbeddingModelEvaluationSpec(
        provider=metadata.provider,
        model=metadata.model,
        vector_size=metadata.vector_size,
        distance=metadata.supported_distances[0],
        fixture_name=fixture_name,
    )


def _repository_settings(session: Session, repository_id: str) -> RepositorySettings:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        raise RuntimeError("Repository settings are unavailable for vector evaluation.")
    return RepositorySettings.model_validate(repository.settings.settings).model_copy(deep=True)


def _apply_embedding_settings(
    session: Session,
    repository_id: str,
    spec: EmbeddingModelEvaluationSpec,
) -> None:
    settings = _repository_settings(session, repository_id)
    settings.embedding.provider = spec.provider  # type: ignore[assignment]
    settings.embedding.model = spec.model
    settings.vector.vector_size = spec.vector_size
    settings.vector.distance = spec.distance  # type: ignore[assignment]
    _save_repository_settings(session, repository_id, settings)


def _save_repository_settings(
    session: Session,
    repository_id: str,
    settings: RepositorySettings,
) -> None:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        raise RuntimeError("Repository settings are unavailable for vector evaluation.")
    repository.settings.settings = settings.model_dump(mode="json")
    session.add(repository.settings)
    session.commit()


def _skipped_result(
    spec: EmbeddingModelEvaluationSpec,
    exc: Exception,
) -> EmbeddingModelEvaluationResult:
    return EmbeddingModelEvaluationResult(
        provider=spec.provider,
        model=spec.model,
        vector_size=spec.vector_size,
        distance=spec.distance,
        fixture_name=spec.fixture_name,
        status="skipped",
        skipped_reason=_skip_reason(spec, exc),
    )


def _skip_reason(
    spec: EmbeddingModelEvaluationSpec,
    exc: Exception,
) -> str:
    message = str(exc)
    if message:
        return message
    if spec.provider == "ollama":
        return f"Start Ollama and run `ollama pull {spec.model}`."
    return f"Cache or install embedding model '{spec.model}' before running live evaluation."
