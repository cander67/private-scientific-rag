from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from private_rag.core.settings import Settings


class ChunkingSettings(BaseModel):
    chunk_size: int = Field(default=800, ge=100, le=8000)
    chunk_overlap: int = Field(default=120, ge=0)
    mode: Literal["recursive", "semantic", "fixed"] = "recursive"


class ParserSettings(BaseModel):
    structured_parser: str = Field(default="pymupdf", min_length=1)
    fallback_parser: str = Field(default="pypdf", min_length=1)


class FullTextSettings(BaseModel):
    tokenizer: Literal["unicode61", "porter"] = "unicode61"
    prefix_index: bool = True
    porter_stemming: bool = False


class VectorSettings(BaseModel):
    collection_name: str = Field(default="default_repository", min_length=1)
    vector_size: int = Field(default=384, ge=1)
    distance: Literal["cosine", "dot", "euclid"] = "cosine"


class EmbeddingSettings(BaseModel):
    provider: Literal["sentence_transformers", "ollama"] = "sentence_transformers"
    model: str = Field(min_length=1)


class RerankingSettings(BaseModel):
    strategy: Literal["cross_encoder", "none"] = "cross_encoder"
    model: str | None = Field(default=None, min_length=1)


class ModelSettings(BaseModel):
    ollama_chat_model: str = Field(min_length=1)


DEFAULT_RAG_CHAT_PROMPT_ID = "rag-chat-default-v1"
DEFAULT_RAG_CHAT_PROMPT = """You are a local scientific RAG assistant. Answer only from the provided repository context.
Use inline citations in square brackets for every factual claim, such as [1] or [2].
If the context does not support an answer, say that the repository context does not contain enough evidence."""


class PromptLibraryEntry(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    text: str = Field(min_length=1)


class PromptSettings(BaseModel):
    version: str = "default-v1"
    active_chat_prompt_id: str = DEFAULT_RAG_CHAT_PROMPT_ID
    library: list[PromptLibraryEntry] = Field(
        default_factory=lambda: [
            PromptLibraryEntry(
                id=DEFAULT_RAG_CHAT_PROMPT_ID,
                name="Repository-grounded chat",
                text=DEFAULT_RAG_CHAT_PROMPT,
            )
        ]
    )

    @model_validator(mode="after")
    def validate_active_prompt(self) -> PromptSettings:
        prompt_ids = {entry.id for entry in self.library}
        if self.active_chat_prompt_id not in prompt_ids:
            raise ValueError("active_chat_prompt_id must reference a prompt library entry")
        return self

    @property
    def active_chat_prompt(self) -> PromptLibraryEntry:
        for entry in self.library:
            if entry.id == self.active_chat_prompt_id:
                return entry
        raise ValueError("active_chat_prompt_id must reference a prompt library entry")


class ExportSettings(BaseModel):
    include_sources: bool = True
    include_indexes: bool = False
    format: Literal["json"] = "json"


class RepositorySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    parser: ParserSettings = Field(default_factory=ParserSettings)
    full_text: FullTextSettings = Field(default_factory=FullTextSettings)
    vector: VectorSettings = Field(default_factory=VectorSettings)
    embedding: EmbeddingSettings
    reranking: RerankingSettings
    model: ModelSettings
    prompt: PromptSettings = Field(default_factory=PromptSettings)
    export: ExportSettings = Field(default_factory=ExportSettings)

    @classmethod
    def from_app_settings(cls, settings: Settings) -> RepositorySettings:
        return cls(
            embedding=EmbeddingSettings(model=settings.default_embedding_model),
            reranking=RerankingSettings(model=settings.default_reranker),
            model=ModelSettings(ollama_chat_model=settings.default_llm),
        )

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> RepositorySettings:
        if self.chunking.chunk_overlap >= self.chunking.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if self.reranking.strategy == "cross_encoder" and not self.reranking.model:
            raise ValueError("reranking.model is required when strategy is cross_encoder")
        if self.vector.distance == "dot" and self.embedding.provider == "ollama":
            raise ValueError("Ollama embeddings currently require cosine distance")
        return self


class RepositoryRead(BaseModel):
    id: str
    name: str
    root_path: str | None = None
    created_at: datetime
    updated_at: datetime


class RepositoryWithSettings(BaseModel):
    repository: RepositoryRead
    settings: RepositorySettings


class RepositorySettingsUpdate(BaseModel):
    settings: RepositorySettings


class RepositorySettingsImpactRequest(BaseModel):
    settings: RepositorySettings


class RepositorySettingsImpact(BaseModel):
    category: Literal[
        "document_reprocessing",
        "full_text_rebuild",
        "vector_rebuild",
        "retrieval_defaults",
        "chat_defaults",
        "prompt_defaults",
        "export_recreate",
        "evaluation_freshness",
    ]
    severity: Literal["info", "warning"] = "warning"
    title: str
    message: str
    fields: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class RepositorySettingsImpactResponse(BaseModel):
    has_changes: bool
    impacts: list[RepositorySettingsImpact] = Field(default_factory=list)


class RepositorySettingsReadinessItem(BaseModel):
    target: Literal["qdrant", "chat", "embedding", "reranker"]
    label: str
    status: Literal[
        "not_checked",
        "unavailable_runtime",
        "not_installed",
        "ready",
        "failed",
        "skipped",
    ]
    ready: bool
    message: str
    model: str | None = None


class RepositorySettingsReadinessResponse(BaseModel):
    repository_id: str
    checked: bool
    items: list[RepositorySettingsReadinessItem]


class RepositoryDashboardCounts(BaseModel):
    documents: int = 0
    parsed_documents: int = 0
    chunks: int = 0
    chat_sessions: int = 0
    chat_messages: int = 0
    retrieval_runs: int = 0
    sandbox_runs: int = 0
    sandbox_comparisons: int = 0
    exports: int = 0
    recreate_events: int = 0


class RepositoryDashboardIndexStatus(BaseModel):
    ready: bool
    status: Literal["ready", "missing", "partial", "stale"]
    message: str
    indexed_chunks: int
    parsed_chunks: int
    model: str | None = None


class RepositoryDashboardActiveConfig(BaseModel):
    chunking: ChunkingSettings
    full_text: FullTextSettings
    vector: VectorSettings
    embedding: EmbeddingSettings
    reranking: RerankingSettings
    chat_model: str
    active_chat_prompt_id: str
    active_chat_prompt_name: str


class RepositoryDashboardActivityItem(BaseModel):
    kind: Literal["document", "retrieval", "chat", "sandbox", "export", "recreate"]
    label: str
    detail: str
    occurred_at: datetime
    route: Literal[
        "documents",
        "search",
        "chat",
        "sandbox",
        "export",
        "recreate",
    ]


class RepositoryDashboardSummary(BaseModel):
    repository: RepositoryRead
    counts: RepositoryDashboardCounts
    full_text: RepositoryDashboardIndexStatus
    vector: RepositoryDashboardIndexStatus
    settings_readiness: RepositorySettingsReadinessResponse
    active_config: RepositoryDashboardActiveConfig
    recent_activity: list[RepositoryDashboardActivityItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RepositoryManifest(BaseModel):
    schema_version: int = 1
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    repository: RepositoryRead
    settings: RepositorySettings
    source_files: list[str] = Field(default_factory=list)


class RecreateValidationRequest(BaseModel):
    manifest: RepositoryManifest
    available_models: list[str] = Field(default_factory=list)


class RecreateValidationIssue(BaseModel):
    code: str
    message: str
    path: str | None = None
    setting: str | None = None


class RecreateValidationResponse(BaseModel):
    can_recreate: bool
    missing_source_files: list[RecreateValidationIssue] = Field(default_factory=list)
    missing_models: list[RecreateValidationIssue] = Field(default_factory=list)
    incompatible_settings: list[RecreateValidationIssue] = Field(default_factory=list)

    @property
    def issues(self) -> list[RecreateValidationIssue]:
        return [
            *self.missing_source_files,
            *self.missing_models,
            *self.incompatible_settings,
        ]


def source_file_exists(path: str) -> bool:
    return Path(path).expanduser().exists()
