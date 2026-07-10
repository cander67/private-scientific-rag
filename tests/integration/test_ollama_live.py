from __future__ import annotations

import os

import pytest

from private_rag.chat.llm import ChatMessage, OllamaChatLLM
from private_rag.core.settings import get_settings


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1")
def test_ollama_gemma3_live_smoke() -> None:
    settings = get_settings()
    llm = OllamaChatLLM(base_url=settings.ollama_base_url, timeout=120)

    completion = llm.complete(
        model=settings.default_llm,
        messages=[
            ChatMessage(
                role="user",
                content=(
                    "You have one source: [1] local setup note. "
                    "Reply in one short sentence and cite [1]."
                ),
            )
        ],
    )

    assert completion.content.strip()
    assert "[1]" in completion.content
