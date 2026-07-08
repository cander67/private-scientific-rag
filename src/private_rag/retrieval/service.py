from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import RepositorySettings
from private_rag.retrieval.models import RetrievalResult, RetrievalRun
from private_rag.retrieval.schemas import (
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalSearchResult,
)
from private_rag.search.schemas import FullTextSearchResult
from private_rag.search.service import search_full_text
from private_rag.vector.embeddings import EmbeddingProvider
from private_rag.vector.schemas import VectorSearchResult
from private_rag.vector.service import search_vector_index
from private_rag.vector.store import VectorStore

MAX_RETRIEVAL_HISTORIES_PER_REPOSITORY = 5


def search_retrieval(
    session: Session,
    repository_id: str,
    request: RetrievalSearchRequest,
    store: VectorStore,
    embedder: EmbeddingProvider,
) -> RetrievalSearchResponse | None:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None

    candidate_pool_size = request.candidate_pool_size or request.top_k * 5
    settings = RepositorySettings.model_validate(repository.settings.settings)

    if request.mode == "full_text":
        full_text_response = search_full_text(
            session=session,
            repository_id=repository_id,
            query=request.query,
            limit=request.top_k,
            filters=request.filters,
        )
        if full_text_response is None:
            return None
        results = [_from_full_text_result(result) for result in full_text_response.results]
    elif request.mode == "vector":
        vector_response = search_vector_index(
            session=session,
            repository_id=repository_id,
            query=request.query,
            limit=request.top_k,
            filters=request.filters,
            store=store,
            embedder=embedder,
        )
        if vector_response is None:
            return None
        results = [_from_vector_result(result) for result in vector_response.results]
    else:
        raise NotImplementedError("Hybrid retrieval will be added in the RRF slice.")

    run = RetrievalRun(
        repository_id=repository_id,
        mode=request.mode,
        query=request.query,
        filters=request.filters.model_dump(mode="json"),
        top_k=request.top_k,
        candidate_pool_size=candidate_pool_size,
        rrf_constant=request.rrf_constant,
        embedding_model=_first_value(result.embedding_model for result in results),
        embedding_run_id=_first_value(result.embedding_run_id for result in results),
        vector_collection_name=_first_value(result.collection_name for result in results),
        reranker_strategy=request.reranker_strategy,
        reranker_model=settings.reranking.model,
        metadata_boosts=request.metadata_boosts.model_dump(mode="json"),
        settings_snapshot=settings.model_dump(mode="json"),
    )
    session.add(run)
    session.flush()

    for result in results:
        session.add(
            RetrievalResult(
                run_id=run.id,
                repository_id=repository_id,
                document_id=result.document_id,
                document_version_id=result.document_version_id,
                chunk_id=result.chunk_id,
                chunk_index=result.chunk_index,
                rank=result.rank,
                final_score=result.final_score,
                score_breakdown=result.score_breakdown,
                source_ranks=result.source_ranks,
                matched_fields=result.matched_fields,
                result_metadata=result.metadata,
            )
        )

    _trim_old_runs(session, repository_id)
    session.commit()
    session.refresh(run)

    return RetrievalSearchResponse(
        run_id=run.id,
        query=request.query,
        repository_id=repository_id,
        mode=request.mode,
        top_k=request.top_k,
        candidate_pool_size=candidate_pool_size,
        rrf_constant=request.rrf_constant,
        reranker_strategy=request.reranker_strategy,
        results=results,
    )


def _from_full_text_result(result: FullTextSearchResult) -> RetrievalSearchResult:
    score = float(result.score)
    return RetrievalSearchResult(
        rank=result.rank,
        final_score=abs(score),
        score_breakdown={"bm25": score},
        source_ranks={"full_text": result.rank, "vector": None},
        repository_id=result.repository_id,
        document_id=result.document_id,
        document_version_id=result.document_version_id,
        chunk_id=result.chunk_id,
        chunk_index=result.chunk_index,
        document_title=result.document_title,
        section=result.section,
        page_start=result.page_start,
        page_end=result.page_end,
        line_start=result.line_start,
        line_end=result.line_end,
        snippet=result.snippet,
        matched_fields=list(result.matched_fields),
        metadata=dict(result.metadata),
    )


def _from_vector_result(result: VectorSearchResult) -> RetrievalSearchResult:
    score = float(result.score)
    return RetrievalSearchResult(
        rank=result.rank,
        final_score=score,
        score_breakdown={"dense": score},
        source_ranks={"full_text": None, "vector": result.rank},
        repository_id=result.repository_id,
        document_id=result.document_id,
        document_version_id=result.document_version_id,
        chunk_id=result.chunk_id,
        chunk_index=result.chunk_index,
        document_title=result.document_title,
        section=result.section,
        page_start=result.page_start,
        page_end=result.page_end,
        line_start=result.line_start,
        line_end=result.line_end,
        text_preview=result.text_preview,
        metadata=dict(result.metadata),
        embedding_run_id=result.embedding_run_id,
        embedding_provider=result.embedding_provider,
        embedding_model=result.embedding_model,
        vector_size=result.vector_size,
        collection_name=result.collection_name,
    )


def _trim_old_runs(session: Session, repository_id: str) -> None:
    retained_ids = list(
        session.scalars(
            select(RetrievalRun.id)
            .where(RetrievalRun.repository_id == repository_id)
            .order_by(RetrievalRun.created_at.desc(), RetrievalRun.id.desc())
            .limit(MAX_RETRIEVAL_HISTORIES_PER_REPOSITORY)
        )
    )
    if not retained_ids:
        return
    session.execute(
        delete(RetrievalRun).where(
            RetrievalRun.repository_id == repository_id,
            RetrievalRun.id.not_in(retained_ids),
        )
    )


def _first_value(values: Iterable[object | None]) -> str | None:
    for value in values:
        if value:
            return str(value)
    return None
