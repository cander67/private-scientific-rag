from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends

from private_rag.api.routes.repositories import DbSession
from private_rag.api.routes.vector import EmbeddingProviderDependency, VectorStoreDependency
from private_rag.retrieval.rerankers import (
    CrossEncoderModelMissingError,
    RerankerProvider,
    SentenceTransformersCrossEncoderProvider,
)
from private_rag.retrieval.schemas import RetrievalSearchRequest, RetrievalSearchResponse
from private_rag.retrieval.service import search_retrieval
from private_rag.vector.service import VectorIndexMissingError
from private_rag.vector.store import VectorStoreError

router = APIRouter(prefix="/repositories/{repository_id}/retrieval", tags=["retrieval"])


def get_reranker_provider() -> Generator[RerankerProvider, None, None]:
    yield SentenceTransformersCrossEncoderProvider()


RerankerProviderDependency = Annotated[RerankerProvider, Depends(get_reranker_provider)]


@router.post("/search", response_model=RetrievalSearchResponse)
def search_repository_retrieval(
    repository_id: str,
    request: RetrievalSearchRequest,
    session: DbSession,
    store: VectorStoreDependency,
    embedder: EmbeddingProviderDependency,
    reranker: RerankerProviderDependency,
) -> RetrievalSearchResponse:
    try:
        response = search_retrieval(
            session=session,
            repository_id=repository_id,
            request=request,
            store=store,
            embedder=embedder,
            reranker=reranker,
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except CrossEncoderModelMissingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VectorIndexMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RuntimeError, VectorStoreError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return response
