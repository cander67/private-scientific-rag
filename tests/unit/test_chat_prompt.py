from __future__ import annotations

from private_rag.chat.llm import ChatMessage
from private_rag.chat.service import MAX_HISTORY_MESSAGES, build_chat_prompt
from private_rag.retrieval.schemas import RetrievalSearchResult


def test_build_chat_prompt_labels_context_and_keeps_recent_history() -> None:
    history = [
        ChatMessage(role="user", content=f"question {index}")
        for index in range(MAX_HISTORY_MESSAGES + 2)
    ]
    result = RetrievalSearchResult(
        rank=1,
        final_score=1.0,
        score_breakdown={"rerank": 1.0},
        source_ranks={"full_text": 1, "vector": 1},
        repository_id="repo-1",
        document_id="doc-1",
        document_version_id="version-1",
        chunk_id="chunk-1",
        chunk_index=4,
        document_title="Catalyst Study",
        section="Methods",
        page_start=3,
        page_end=4,
        line_start=None,
        line_end=None,
        snippet="The measured selectivity was 58.",
    )

    messages = build_chat_prompt(
        system_prompt="Answer from context.",
        history=history,
        question="What was measured?",
        context_results=[result],
    )

    assert messages[0].role == "system"
    assert "[1] Catalyst Study, chunk 4, pages 3-4, section Methods" in messages[0].content
    assert "The measured selectivity was 58." in messages[0].content
    assert messages[1].content == "question 2"
    assert messages[-1] == ChatMessage(role="user", content="What was measured?")
