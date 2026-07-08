from __future__ import annotations

from fastapi import APIRouter, HTTPException

from private_rag.api.routes.repositories import DbSession
from private_rag.api.routes.vector import EmbeddingProviderDependency, VectorStoreDependency
from private_rag.retrieval.schemas import RetrievalSearchRequest, RetrievalSearchResponse
from private_rag.retrieval.service import search_retrieval
from private_rag.vector.service import VectorIndexMissingError
from private_rag.vector.store import VectorStoreError

router = APIRouter(prefix="/repositories/{repository_id}/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalSearchResponse)
def search_repository_retrieval(
    repository_id: str,
    request: RetrievalSearchRequest,
    session: DbSession,
    store: VectorStoreDependency,
    embedder: EmbeddingProviderDependency,
) -> RetrievalSearchResponse:
    try:
        response = search_retrieval(
            session=session,
            repository_id=repository_id,
            request=request,
            store=store,
            embedder=embedder,
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except VectorIndexMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RuntimeError, VectorStoreError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return response
