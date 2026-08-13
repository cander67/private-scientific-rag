from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TokenizerProvider = Literal["sentence_transformers", "ollama", "openai", "private_rag"]
TokenizerPrecision = Literal["exact", "fallback"]
TokenizerImplementationLibrary = Literal["transformers", "tiktoken", "regex"]

FALLBACK_TOKENIZER_ID = "private-rag/simple-token-fallback-v1"


@dataclass(frozen=True)
class TokenizerCatalogEntry:
    id: str
    label: str
    provider: TokenizerProvider
    implementation_library: TokenizerImplementationLibrary
    tokenizer_name: str
    tokenizer_source: str
    precision: TokenizerPrecision
    offset_mapping: bool
    requires_local_model: bool
    is_fallback: bool
    notes: str
    fallback_warning: str | None = None


TOKENIZER_CATALOG: tuple[TokenizerCatalogEntry, ...] = (
    TokenizerCatalogEntry(
        id="hf:sentence-transformers/all-MiniLM-L6-v2",
        label="SentenceTransformers MiniLM tokenizer",
        provider="sentence_transformers",
        implementation_library="transformers",
        tokenizer_name="sentence-transformers/all-MiniLM-L6-v2",
        tokenizer_source="sentence_transformers_model",
        precision="exact",
        offset_mapping=True,
        requires_local_model=True,
        is_fallback=False,
        notes="Exact HuggingFace tokenizer for the MiniLM embedding model when cached locally.",
    ),
    TokenizerCatalogEntry(
        id="hf:sentence-transformers/all-mpnet-base-v2",
        label="SentenceTransformers MPNet tokenizer",
        provider="sentence_transformers",
        implementation_library="transformers",
        tokenizer_name="sentence-transformers/all-mpnet-base-v2",
        tokenizer_source="sentence_transformers_model",
        precision="exact",
        offset_mapping=True,
        requires_local_model=True,
        is_fallback=False,
        notes="Exact HuggingFace tokenizer for the MPNet embedding model when cached locally.",
    ),
    TokenizerCatalogEntry(
        id="tiktoken:cl100k_base",
        label="OpenAI cl100k_base",
        provider="openai",
        implementation_library="tiktoken",
        tokenizer_name="cl100k_base",
        tokenizer_source="tiktoken_encoding",
        precision="exact",
        offset_mapping=True,
        requires_local_model=False,
        is_fallback=False,
        notes="Exact tiktoken encoding used by many OpenAI chat and embedding models.",
    ),
    TokenizerCatalogEntry(
        id="tiktoken:o200k_base",
        label="OpenAI o200k_base",
        provider="openai",
        implementation_library="tiktoken",
        tokenizer_name="o200k_base",
        tokenizer_source="tiktoken_encoding",
        precision="exact",
        offset_mapping=True,
        requires_local_model=False,
        is_fallback=False,
        notes="Exact tiktoken encoding used by newer OpenAI models.",
    ),
    TokenizerCatalogEntry(
        id=FALLBACK_TOKENIZER_ID,
        label="Simple regex fallback",
        provider="private_rag",
        implementation_library="regex",
        tokenizer_name=FALLBACK_TOKENIZER_ID,
        tokenizer_source="app_fallback",
        precision="fallback",
        offset_mapping=True,
        requires_local_model=False,
        is_fallback=True,
        notes="Deterministic fallback that counts word-like runs and individual punctuation/symbol tokens.",
        fallback_warning="Approximate regex tokenizer; use only when an exact model tokenizer is unavailable.",
    ),
)


def known_tokenizer_catalog() -> tuple[TokenizerCatalogEntry, ...]:
    return TOKENIZER_CATALOG


def lookup_tokenizer_catalog_entry(tokenizer_id: str) -> TokenizerCatalogEntry | None:
    for entry in TOKENIZER_CATALOG:
        if entry.id == tokenizer_id:
            return entry
    return None


def huggingface_tokenizer_id(model: str) -> str:
    return f"hf:{model}"
