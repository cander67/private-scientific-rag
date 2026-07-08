from __future__ import annotations

import pytest

from private_rag.retrieval.service import merge_rrf_results
from private_rag.search.schemas import FullTextSearchResult
from private_rag.vector.schemas import VectorSearchResult


def _full_text_result(chunk_id: str, rank: int, score: float = -1.0) -> FullTextSearchResult:
    return FullTextSearchResult(
        rank=rank,
        score=score,
        repository_id="repo-1",
        document_id=f"doc-{chunk_id}",
        document_version_id=f"version-{chunk_id}",
        chunk_id=chunk_id,
        chunk_index=rank - 1,
        document_title=f"{chunk_id}.txt",
        snippet=f"<mark>{chunk_id}</mark>",
        matched_fields=["body"],
        metadata={"source_type": "text"},
    )


def _vector_result(chunk_id: str, rank: int, score: float = 0.8) -> VectorSearchResult:
    return VectorSearchResult(
        rank=rank,
        score=score,
        distance="cosine",
        repository_id="repo-1",
        document_id=f"doc-{chunk_id}",
        document_version_id=f"version-{chunk_id}",
        chunk_id=chunk_id,
        chunk_index=rank - 1,
        document_title=f"{chunk_id}.txt",
        text_preview=f"{chunk_id} preview",
        metadata={"source_type": "text"},
        embedding_run_id="embedding-run-1",
        embedding_provider="sentence_transformers",
        embedding_model="test-deterministic",
        vector_size=8,
        collection_name="repository_repo_1_latest",
    )


def test_rrf_merge_prefers_overlapping_candidates() -> None:
    results = merge_rrf_results(
        [_full_text_result("sparse-only", 1), _full_text_result("overlap", 2)],
        [_vector_result("overlap", 1), _vector_result("dense-only", 2)],
        rrf_constant=60,
        limit=3,
    )

    assert [result.chunk_id for result in results] == ["overlap", "sparse-only", "dense-only"]
    assert results[0].source_ranks == {"full_text": 2, "vector": 1}
    assert results[0].score_breakdown["bm25"] == -1.0
    assert results[0].score_breakdown["dense"] == 0.8
    assert results[0].score_breakdown["rrf"] == pytest.approx(1 / 62 + 1 / 61)
    assert results[1].source_ranks == {"full_text": 1, "vector": None}
    assert results[2].source_ranks == {"full_text": None, "vector": 2}


def test_rrf_merge_honors_limit_and_adjustable_constant() -> None:
    default_results = merge_rrf_results(
        [_full_text_result("a", 1)],
        [_vector_result("a", 1)],
        rrf_constant=60,
        limit=1,
    )
    adjusted_results = merge_rrf_results(
        [_full_text_result("a", 1)],
        [_vector_result("a", 1)],
        rrf_constant=10,
        limit=1,
    )

    assert len(default_results) == 1
    assert adjusted_results[0].score_breakdown["rrf"] > default_results[0].score_breakdown["rrf"]
