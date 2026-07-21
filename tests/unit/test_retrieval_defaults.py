from __future__ import annotations

from private_rag.chat.schemas import ChatRetrievalSettings
from private_rag.retrieval.defaults import (
    normalize_retrieval_defaults,
    resolve_effective_retrieval_settings,
)
from private_rag.retrieval.schemas import MetadataBoostSettings, RetrievalDefaults


def test_normalizes_old_chat_settings_with_new_defaults() -> None:
    settings = normalize_retrieval_defaults(
        {"mode": "hybrid", "top_k": 3, "reranker_strategy": "none"},
        defaults_type=ChatRetrievalSettings,
    )

    assert settings.mode == "hybrid"
    assert settings.top_k == 3
    assert settings.reranker_strategy == "none"
    assert settings.candidate_pool_size is None
    assert settings.rrf_constant == 60
    assert settings.metadata_boosts == MetadataBoostSettings()


def test_resolves_effective_settings_with_field_sources() -> None:
    effective = resolve_effective_retrieval_settings(
        fallback_defaults=ChatRetrievalSettings(),
        repository_defaults=RetrievalDefaults(
            mode="hybrid",
            top_k=8,
            candidate_pool_size=40,
            reranker_strategy="metadata_boost",
        ),
        session_defaults={"top_k": 4},
        run_overrides={
            "metadata_boosts": {"section": "off"},
            "filters": {"document_kind": "patent_pdf"},
        },
    )

    assert effective.settings.mode == "hybrid"
    assert effective.settings.top_k == 4
    assert effective.settings.candidate_pool_size == 40
    assert effective.settings.metadata_boosts.section == "off"
    assert effective.settings.metadata_boosts.document_kind == "low"
    assert effective.settings.filters.document_kind == "patent_pdf"
    assert effective.sources["mode"] == "repository_defaults"
    assert effective.sources["top_k"] == "session_defaults"
    assert effective.sources["candidate_pool_size"] == "repository_defaults"
    assert effective.sources["metadata_boosts.section"] == "run_override"
    assert effective.sources["metadata_boosts.document_kind"] == "fallback_defaults"
    assert effective.sources["filters.document_kind"] == "run_override"
