from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PRIVATE_RAG_",
        extra="ignore",
    )

    environment: str = Field(
        default="local",
        validation_alias=AliasChoices("PRIVATE_RAG_ENV", "PRIVATE_RAG_ENVIRONMENT", "ENV"),
    )
    data_dir: Path = Path("./data")
    database_url: str = "sqlite:///./data/private_rag.sqlite"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias=AliasChoices("PRIVATE_RAG_CORS_ORIGINS", "CORS_ORIGINS"),
    )
    qdrant_url: str = "http://localhost:6333"
    ollama_base_url: str = "http://localhost:11434"
    default_llm: str = "gemma3:4b"
    default_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    default_reranker: str = "cross-encoder/ms-marco-MiniLM-L6-v2"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def safe_database_url(self) -> str:
        if self.database_url.startswith("sqlite"):
            return self.database_url
        return "<configured>"


@lru_cache
def get_settings() -> Settings:
    return Settings()
