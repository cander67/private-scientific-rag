from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from private_rag.api.routes.repositories import DbSession
from private_rag.ingestion.schemas import DocumentInspection, DocumentRead, DocumentUploadResponse
from private_rag.ingestion.service import (
    delete_document,
    inspect_document,
    list_documents,
    reprocess_document,
    upload_document,
)

router = APIRouter(prefix="/repositories/{repository_id}/documents", tags=["documents"])


@router.post("", response_model=DocumentUploadResponse)
async def upload_repository_document(
    repository_id: str,
    session: DbSession,
    file: Annotated[UploadFile, File()],
) -> DocumentUploadResponse:
    data = await file.read()
    uploaded = upload_document(
        session=session,
        repository_id=repository_id,
        filename=file.filename or "document",
        content_type=file.content_type,
        data=data,
    )
    if uploaded is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return uploaded


@router.get("", response_model=list[DocumentRead])
def read_repository_documents(
    repository_id: str,
    session: DbSession,
) -> list[DocumentRead]:
    documents = list_documents(session, repository_id)
    if documents is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return documents


@router.get("/{document_id}", response_model=DocumentInspection)
def inspect_repository_document(
    repository_id: str,
    document_id: str,
    session: DbSession,
) -> DocumentInspection:
    inspection = inspect_document(session, repository_id, document_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return inspection


@router.post("/{document_id}/reprocess", response_model=DocumentInspection)
def reprocess_repository_document(
    repository_id: str,
    document_id: str,
    session: DbSession,
) -> DocumentInspection:
    inspection = reprocess_document(session, repository_id, document_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return inspection


@router.delete("/{document_id}", status_code=204)
def delete_repository_document(
    repository_id: str,
    document_id: str,
    session: DbSession,
) -> None:
    deleted = delete_document(session, repository_id, document_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Document not found")
