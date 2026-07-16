from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import RepositorySettings
from private_rag.retrieval.models import RetrievalResult, RetrievalRun
from private_rag.retrieval.rerankers import RerankerProvider
from private_rag.retrieval.schemas import (
    MetadataBoostSettings,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalSearchResult,
)
from private_rag.search.schemas import FullTextSearchResult
from private_rag.search.service import search_full_text
from private_rag.vector.embeddings import EmbeddingProviderSource
from private_rag.vector.schemas import VectorSearchResult
from private_rag.vector.service import search_vector_index
from private_rag.vector.store import VectorStore

MAX_RETRIEVAL_HISTORIES_PER_REPOSITORY = 5


def search_retrieval(
    session: Session,
    repository_id: str,
    request: RetrievalSearchRequest,
    store: VectorStore,
    embedder: EmbeddingProviderSource,
    reranker: RerankerProvider,
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
        full_text_response = search_full_text(
            session=session,
            repository_id=repository_id,
            query=request.query,
            limit=candidate_pool_size,
            filters=request.filters,
        )
        if full_text_response is None:
            return None
        vector_response = search_vector_index(
            session=session,
            repository_id=repository_id,
            query=request.query,
            limit=candidate_pool_size,
            filters=request.filters,
            store=store,
            embedder=embedder,
        )
        if vector_response is None:
            return None
        results = merge_rrf_results(
            full_text_response.results,
            vector_response.results,
            rrf_constant=request.rrf_constant,
            limit=request.top_k,
        )

    results = apply_reranking(
        query=request.query,
        results=results,
        strategy=request.reranker_strategy,
        metadata_boosts=request.metadata_boosts,
        reranker=reranker,
        reranker_model=settings.reranking.model,
    )

    uses_cross_encoder = request.reranker_strategy in {
        "cross_encoder",
        "cross_encoder_metadata_boost",
    }
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
        reranker_model=settings.reranking.model if uses_cross_encoder else None,
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


@dataclass
class _HybridCandidate:
    chunk_id: str
    full_text: FullTextSearchResult | None = None
    vector: VectorSearchResult | None = None


def merge_rrf_results(
    full_text_results: list[FullTextSearchResult],
    vector_results: list[VectorSearchResult],
    *,
    rrf_constant: int,
    limit: int,
) -> list[RetrievalSearchResult]:
    candidates: dict[str, _HybridCandidate] = {}
    for full_text_result in full_text_results:
        candidate = candidates.setdefault(
            full_text_result.chunk_id,
            _HybridCandidate(chunk_id=full_text_result.chunk_id),
        )
        candidate.full_text = full_text_result
    for vector_result in vector_results:
        candidate = candidates.setdefault(
            vector_result.chunk_id,
            _HybridCandidate(chunk_id=vector_result.chunk_id),
        )
        candidate.vector = vector_result

    ranked = sorted(
        (_from_hybrid_candidate(candidate, rrf_constant) for candidate in candidates.values()),
        key=lambda result: result.score_breakdown["rrf"],
        reverse=True,
    )
    return [
        result.model_copy(update={"rank": rank, "final_score": result.score_breakdown["rrf"]})
        for rank, result in enumerate(ranked[:limit], start=1)
    ]


def _from_hybrid_candidate(
    candidate: _HybridCandidate,
    rrf_constant: int,
) -> RetrievalSearchResult:
    full_text = candidate.full_text
    vector = candidate.vector
    source = full_text or vector
    if source is None:
        raise ValueError("Hybrid candidate must have at least one retrieval source.")

    full_text_rank = full_text.rank if full_text else None
    vector_rank = vector.rank if vector else None
    rrf_score = _rrf_score(full_text_rank, vector_rank, rrf_constant)
    score_breakdown = {
        "bm25": full_text.score if full_text else None,
        "dense": vector.score if vector else None,
        "rrf": rrf_score,
    }

    return RetrievalSearchResult(
        rank=0,
        final_score=rrf_score,
        score_breakdown=score_breakdown,
        source_ranks={"full_text": full_text_rank, "vector": vector_rank},
        repository_id=source.repository_id,
        document_id=source.document_id,
        document_version_id=source.document_version_id,
        chunk_id=source.chunk_id,
        chunk_index=source.chunk_index,
        document_title=source.document_title,
        section=source.section,
        page_start=source.page_start,
        page_end=source.page_end,
        line_start=source.line_start,
        line_end=source.line_end,
        snippet=full_text.snippet if full_text else None,
        text_preview=vector.text_preview if vector else None,
        matched_fields=list(full_text.matched_fields) if full_text else [],
        metadata=dict(source.metadata),
        embedding_run_id=vector.embedding_run_id if vector else None,
        embedding_provider=vector.embedding_provider if vector else None,
        embedding_model=vector.embedding_model if vector else None,
        vector_size=vector.vector_size if vector else None,
        collection_name=vector.collection_name if vector else None,
    )


def _rrf_score(
    full_text_rank: int | None,
    vector_rank: int | None,
    rrf_constant: int,
) -> float:
    score = 0.0
    if full_text_rank is not None:
        score += 1.0 / (rrf_constant + full_text_rank)
    if vector_rank is not None:
        score += 1.0 / (rrf_constant + vector_rank)
    return score


def apply_reranking(
    *,
    query: str,
    results: list[RetrievalSearchResult],
    strategy: str,
    metadata_boosts: MetadataBoostSettings,
    reranker: RerankerProvider,
    reranker_model: str | None,
) -> list[RetrievalSearchResult]:
    if strategy == "none" or not results:
        return results

    ranked = results
    if strategy in {"cross_encoder", "cross_encoder_metadata_boost"}:
        if not reranker_model:
            raise RuntimeError("reranking.model is required for cross-encoder reranking.")
        rerank_scores = reranker.score(query, ranked, reranker_model)
        ranked = [
            _with_score(
                result,
                score_name="rerank",
                score=score,
                final_score=score,
            )
            for result, score in zip(ranked, rerank_scores, strict=True)
        ]
        ranked = sorted(ranked, key=lambda result: result.final_score, reverse=True)

    if strategy in {"metadata_boost", "cross_encoder_metadata_boost"}:
        ranked = [_with_metadata_boost(result, metadata_boosts) for result in ranked]
        ranked = sorted(ranked, key=lambda result: result.final_score, reverse=True)

    return [result.model_copy(update={"rank": rank}) for rank, result in enumerate(ranked, start=1)]


def _with_score(
    result: RetrievalSearchResult,
    *,
    score_name: str,
    score: float,
    final_score: float,
) -> RetrievalSearchResult:
    score_breakdown = {**result.score_breakdown, score_name: score}
    return result.model_copy(
        update={"final_score": final_score, "score_breakdown": score_breakdown}
    )


def _with_metadata_boost(
    result: RetrievalSearchResult,
    boosts: MetadataBoostSettings,
) -> RetrievalSearchResult:
    boost = metadata_boost_score(result, boosts)
    score_breakdown = {**result.score_breakdown, "metadata_boost": boost}
    return result.model_copy(
        update={
            "final_score": result.final_score + boost,
            "score_breakdown": score_breakdown,
        }
    )


def metadata_boost_score(
    result: RetrievalSearchResult,
    boosts: MetadataBoostSettings,
) -> float:
    score = 0.0
    if result.section:
        score += _boost_weight(boosts.section)
    if result.metadata.get("document_kind"):
        score += _boost_weight(boosts.document_kind)
    if result.metadata.get("patent_sections"):
        score += _boost_weight(boosts.patent_section)
    if result.metadata.get("has_table") or result.metadata.get("has_figure"):
        score += _boost_weight(boosts.table_figure)
    return score


def _boost_weight(level: str) -> float:
    return {
        "low": 0.05,
        "medium": 0.15,
        "high": 0.3,
    }[level]


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
