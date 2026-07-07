from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from private_rag.api.routes.repositories import DbSession
from private_rag.core.settings import get_settings
from private_rag.vector.embeddings import EmbeddingProvider, SentenceTransformersEmbeddingProvider
from private_rag.vector.schemas import (
    VectorRebuildResponse,
    VectorSearchRequest,
    VectorSearchResponse,
)
from private_rag.vector.service import (
    VectorIndexMissingError,
    rebuild_vector_index,
    search_vector_index,
)
from private_rag.vector.store import QdrantVectorStore, VectorStore, VectorStoreError

router = APIRouter(prefix="/repositories/{repository_id}/vector", tags=["vector search"])


def get_vector_store() -> Generator[VectorStore, None, None]:
    settings = get_settings()
    yield QdrantVectorStore(settings.qdrant_url)


def get_embedding_provider() -> Generator[EmbeddingProvider, None, None]:
    settings = get_settings()
    yield SentenceTransformersEmbeddingProvider(settings.default_embedding_model)


VectorStoreDependency = Annotated[VectorStore, Depends(get_vector_store)]
EmbeddingProviderDependency = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]


@router.post("/rebuild", response_model=VectorRebuildResponse)
def rebuild_repository_vector_index(
    repository_id: str,
    session: DbSession,
    store: VectorStoreDependency,
    embedder: EmbeddingProviderDependency,
) -> VectorRebuildResponse:
    try:
        rebuilt = rebuild_vector_index(session, repository_id, store, embedder)
    except (RuntimeError, VectorStoreError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if rebuilt is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return rebuilt


@router.post("/search", response_model=VectorSearchResponse)
def search_repository_vector_index(
    repository_id: str,
    request: VectorSearchRequest,
    session: DbSession,
    store: VectorStoreDependency,
    embedder: EmbeddingProviderDependency,
) -> VectorSearchResponse:
    try:
        response = search_vector_index(
            session=session,
            repository_id=repository_id,
            query=request.query,
            limit=request.limit,
            filters=request.filters,
            store=store,
            embedder=embedder,
        )
    except VectorIndexMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RuntimeError, VectorStoreError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return response
