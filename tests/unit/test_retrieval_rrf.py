from __future__ import annotations

import pytest

from private_rag.retrieval.schemas import MetadataBoostSettings, RetrievalSearchResult
from private_rag.retrieval.service import apply_reranking, merge_rrf_results
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


class _FakeReranker:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores

    def score(
        self,
        query: str,
        results: list[RetrievalSearchResult],
        model_name: str,
    ) -> list[float]:
        assert query == "adhesive cathode"
        assert model_name == "cross-encoder/test"
        return [self.scores[result.chunk_id] for result in results]


def test_reranking_none_preserves_baseline_order() -> None:
    baseline = merge_rrf_results(
        [_full_text_result("first", 1), _full_text_result("second", 2)],
        [],
        rrf_constant=60,
        limit=2,
    )

    reranked = apply_reranking(
        query="adhesive cathode",
        results=baseline,
        strategy="none",
        metadata_boosts=MetadataBoostSettings(),
        reranker=_FakeReranker({"first": 0.1, "second": 0.9}),
        reranker_model="cross-encoder/test",
    )

    assert [result.chunk_id for result in reranked] == ["first", "second"]


def test_cross_encoder_reranking_changes_order_and_reports_score() -> None:
    baseline = merge_rrf_results(
        [_full_text_result("first", 1), _full_text_result("second", 2)],
        [],
        rrf_constant=60,
        limit=2,
    )

    reranked = apply_reranking(
        query="adhesive cathode",
        results=baseline,
        strategy="cross_encoder",
        metadata_boosts=MetadataBoostSettings(),
        reranker=_FakeReranker({"first": 0.1, "second": 0.9}),
        reranker_model="cross-encoder/test",
    )

    assert [result.chunk_id for result in reranked] == ["second", "first"]
    assert reranked[0].rank == 1
    assert reranked[0].final_score == pytest.approx(0.9)
    assert reranked[0].score_breakdown["rerank"] == pytest.approx(0.9)


def test_metadata_boost_reranking_changes_order_and_reports_boost() -> None:
    unboosted = _full_text_result("unboosted", 1)
    boosted = _full_text_result("boosted", 2)
    boosted.section = "Claims"
    boosted.metadata = {"document_kind": "patent_pdf", "patent_sections": ["claims"]}
    baseline = merge_rrf_results([unboosted, boosted], [], rrf_constant=60, limit=2)

    reranked = apply_reranking(
        query="adhesive cathode",
        results=baseline,
        strategy="metadata_boost",
        metadata_boosts=MetadataBoostSettings(
            section="high",
            document_kind="high",
            patent_section="high",
            table_figure="low",
        ),
        reranker=_FakeReranker({}),
        reranker_model=None,
    )

    assert [result.chunk_id for result in reranked] == ["boosted", "unboosted"]
    assert reranked[0].score_breakdown["metadata_boost"] == pytest.approx(0.9)


def test_combined_reranking_applies_cross_encoder_then_metadata_boost() -> None:
    cross_encoder_winner = _full_text_result("cross-encoder-winner", 1)
    metadata_winner = _full_text_result("metadata-winner", 2)
    metadata_winner.section = "Claims"
    metadata_winner.metadata = {"document_kind": "patent_pdf", "patent_sections": ["claims"]}
    baseline = merge_rrf_results(
        [cross_encoder_winner, metadata_winner],
        [],
        rrf_constant=60,
        limit=2,
    )

    reranked = apply_reranking(
        query="adhesive cathode",
        results=baseline,
        strategy="cross_encoder_metadata_boost",
        metadata_boosts=MetadataBoostSettings(
            section="medium",
            document_kind="medium",
            patent_section="medium",
            table_figure="low",
        ),
        reranker=_FakeReranker({"cross-encoder-winner": 0.8, "metadata-winner": 0.4}),
        reranker_model="cross-encoder/test",
    )

    assert [result.chunk_id for result in reranked] == ["metadata-winner", "cross-encoder-winner"]
    assert reranked[0].score_breakdown["rerank"] == pytest.approx(0.4)
    assert reranked[0].score_breakdown["metadata_boost"] == pytest.approx(0.45)
