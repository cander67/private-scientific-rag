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
    structured_parser: str = "pymupdf"
    fallback_parser: str = "pypdf"


class FullTextSettings(BaseModel):
    tokenizer: Literal["unicode61", "porter"] = "unicode61"
    prefix_index: bool = True
    porter_stemming: bool = False


class VectorSettings(BaseModel):
    collection_name: str = "default_repository"
    vector_size: int = Field(default=384, ge=1)
    distance: Literal["cosine", "dot", "euclid"] = "cosine"


class EmbeddingSettings(BaseModel):
    provider: Literal["sentence_transformers", "ollama"] = "sentence_transformers"
    model: str


class RerankingSettings(BaseModel):
    strategy: Literal["cross_encoder", "none"] = "cross_encoder"
    model: str | None = None


class ModelSettings(BaseModel):
    ollama_chat_model: str


class PromptSettings(BaseModel):
    version: str = "default-v1"


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
