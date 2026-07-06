from __future__ import annotations

from fastapi import APIRouter, HTTPException

from private_rag.api.routes.repositories import DbSession
from private_rag.search.schemas import (
    FullTextRebuildResponse,
    FullTextSearchRequest,
    FullTextSearchResponse,
)
from private_rag.search.service import rebuild_full_text_index, search_full_text

router = APIRouter(prefix="/repositories/{repository_id}/full-text", tags=["full-text search"])


@router.post("/rebuild", response_model=FullTextRebuildResponse)
def rebuild_repository_full_text_index(
    repository_id: str,
    session: DbSession,
) -> FullTextRebuildResponse:
    rebuilt = rebuild_full_text_index(session, repository_id)
    if rebuilt is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return rebuilt


@router.post("/search", response_model=FullTextSearchResponse)
def search_repository_full_text(
    repository_id: str,
    request: FullTextSearchRequest,
    session: DbSession,
) -> FullTextSearchResponse:
    response = search_full_text(
        session=session,
        repository_id=repository_id,
        query=request.query,
        limit=request.limit,
        filters=request.filters,
    )
    if response is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return response
