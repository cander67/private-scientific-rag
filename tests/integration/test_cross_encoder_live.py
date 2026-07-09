from __future__ import annotations

import os

import pytest

from private_rag.retrieval.rerankers import SentenceTransformersCrossEncoderProvider
from private_rag.retrieval.schemas import RetrievalSearchResult


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1")
def test_live_cross_encoder_returns_scores_for_tiny_fixture() -> None:
    provider = SentenceTransformersCrossEncoderProvider()
    results = [
        RetrievalSearchResult(
            rank=1,
            final_score=0.1,
            score_breakdown={"rrf": 0.1},
            source_ranks={"full_text": 1, "vector": None},
            repository_id="repo-1",
            document_id="doc-1",
            document_version_id="version-1",
            chunk_id="chunk-relevant",
            chunk_index=0,
            document_title="relevant.txt",
            text_preview="LiFePO4 cathodes retain capacity during battery cycling.",
        ),
        RetrievalSearchResult(
            rank=2,
            final_score=0.09,
            score_breakdown={"rrf": 0.09},
            source_ranks={"full_text": 2, "vector": None},
            repository_id="repo-1",
            document_id="doc-2",
            document_version_id="version-2",
            chunk_id="chunk-less-relevant",
            chunk_index=1,
            document_title="less-relevant.txt",
            text_preview="Epoxy acrylate adhesives cure under ultraviolet light.",
        ),
    ]

    scores = provider.score(
        "lithium iron phosphate battery cathode",
        results,
        "cross-encoder/ms-marco-MiniLM-L6-v2",
    )

    assert len(scores) == 2
    assert all(isinstance(score, float) for score in scores)
    assert scores[0] != scores[1]
