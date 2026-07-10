from __future__ import annotations

from private_rag.chat.citations import map_citations
from private_rag.retrieval.schemas import RetrievalSearchResult


def _result(rank: int, chunk_id: str) -> RetrievalSearchResult:
    return RetrievalSearchResult(
        rank=rank,
        final_score=1.0,
        score_breakdown={"rerank": 1.0},
        source_ranks={"full_text": rank, "vector": rank},
        repository_id="repo-1",
        document_id=f"doc-{rank}",
        document_version_id=f"version-{rank}",
        chunk_id=chunk_id,
        chunk_index=rank - 1,
        document_title=f"Document {rank}",
        section="Results",
        page_start=rank,
        page_end=rank,
        line_start=10,
        line_end=12,
        snippet=f"snippet {rank}",
        metadata={"has_table": rank == 2},
    )


def test_map_citations_maps_unique_tokens_to_retrieved_chunks() -> None:
    citations = map_citations(
        "The first fact [1] and second fact [2]. More first [1].",
        [
            _result(1, "chunk-a"),
            _result(2, "chunk-b"),
        ],
    )

    assert [citation.citation_id for citation in citations] == [1, 2]
    assert citations[0].chunk_id == "chunk-a"
    assert citations[1].chunk_id == "chunk-b"
    assert citations[1].metadata["has_table"] is True


def test_map_citations_ignores_out_of_range_tokens() -> None:
    citations = map_citations("Supported [1], unsupported [9].", [_result(1, "chunk-a")])

    assert len(citations) == 1
    assert citations[0].token == "[1]"
