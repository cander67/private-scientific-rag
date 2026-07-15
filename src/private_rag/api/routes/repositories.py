from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from private_rag.db.session import SessionLocal
from private_rag.repositories.schemas import (
    RecreateValidationRequest,
    RecreateValidationResponse,
    RepositoryManifest,
    RepositoryRead,
    RepositorySettingsImpactRequest,
    RepositorySettingsImpactResponse,
    RepositorySettingsUpdate,
    RepositoryWithSettings,
)
from private_rag.repositories.service import (
    analyze_repository_settings_impact,
    ensure_default_repository,
    export_manifest,
    get_repository_with_settings,
    list_repositories,
    update_repository_settings,
    validate_recreate_request,
)

router = APIRouter(prefix="/repositories", tags=["repositories"])


def get_db_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("/default", response_model=RepositoryWithSettings)
def read_default_repository(session: DbSession) -> RepositoryWithSettings:
    return ensure_default_repository(session)


@router.get("", response_model=list[RepositoryRead])
def read_repositories(session: DbSession) -> list[RepositoryRead]:
    ensure_default_repository(session)
    return list_repositories(session)


@router.get("/{repository_id}/settings", response_model=RepositoryWithSettings)
def read_repository_settings(
    repository_id: str,
    session: DbSession,
) -> RepositoryWithSettings:
    repository = get_repository_with_settings(session, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository


@router.post("/{repository_id}/settings/impact", response_model=RepositorySettingsImpactResponse)
def preview_repository_settings_impact(
    repository_id: str,
    request: RepositorySettingsImpactRequest,
    session: DbSession,
) -> RepositorySettingsImpactResponse:
    impact = analyze_repository_settings_impact(session, repository_id, request.settings)
    if impact is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return impact


@router.put("/{repository_id}/settings", response_model=RepositoryWithSettings)
def save_repository_settings(
    repository_id: str,
    update: RepositorySettingsUpdate,
    session: DbSession,
) -> RepositoryWithSettings:
    repository = update_repository_settings(session, repository_id, update.settings)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository


@router.get("/{repository_id}/manifest", response_model=RepositoryManifest)
def read_repository_manifest(
    repository_id: str,
    session: DbSession,
) -> RepositoryManifest:
    manifest = export_manifest(session, repository_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return manifest


@router.post("/recreate/validate", response_model=RecreateValidationResponse)
def validate_recreate(request: RecreateValidationRequest) -> RecreateValidationResponse:
    return validate_recreate_request(request)
