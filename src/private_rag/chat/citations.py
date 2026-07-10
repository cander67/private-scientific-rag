from __future__ import annotations

import re

from private_rag.chat.schemas import ChatCitation
from private_rag.retrieval.schemas import RetrievalSearchResult

CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def map_citations(
    answer: str,
    context_results: list[RetrievalSearchResult],
) -> list[ChatCitation]:
    citations: list[ChatCitation] = []
    seen: set[int] = set()
    for match in CITATION_PATTERN.finditer(answer):
        citation_id = int(match.group(1))
        if citation_id in seen:
            continue
        seen.add(citation_id)
        index = citation_id - 1
        if index < 0 or index >= len(context_results):
            continue
        result = context_results[index]
        citations.append(
            ChatCitation(
                citation_id=citation_id,
                token=match.group(0),
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
                metadata=result.metadata,
                retrieval_rank=result.rank,
                score_breakdown=result.score_breakdown,
                text_preview=result.snippet or result.text_preview,
            )
        )
    return citations
