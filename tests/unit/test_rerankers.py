from __future__ import annotations

import pytest

from private_rag.retrieval.rerankers import (
    CrossEncoderModelMissingError,
    SentenceTransformersCrossEncoderProvider,
)
from private_rag.retrieval.schemas import RetrievalSearchResult


def test_cross_encoder_provider_reports_setup_guidance_for_missing_model() -> None:
    provider = SentenceTransformersCrossEncoderProvider()
    result = RetrievalSearchResult(
        rank=1,
        final_score=0.1,
        score_breakdown={"rrf": 0.1},
        source_ranks={"full_text": 1, "vector": None},
        repository_id="repo-1",
        document_id="doc-1",
        document_version_id="version-1",
        chunk_id="chunk-1",
        chunk_index=0,
        document_title="missing-model.txt",
        text_preview="LiFePO4 cathodes retain capacity.",
    )

    with pytest.raises(CrossEncoderModelMissingError) as exc_info:
        provider.score(
            "lithium battery",
            [result],
            "private-rag/definitely-missing-cross-encoder-model",
        )

    message = str(exc_info.value)
    assert "requires a downloaded local model" in message
    assert "private-rag/definitely-missing-cross-encoder-model" in message
