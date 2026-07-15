from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from private_rag.chat.llm import ChatLLM, OllamaChatLLM
from private_rag.core.settings import get_settings
from private_rag.db.session import SessionLocal
from private_rag.repositories.schemas import (
    RecreateValidationRequest,
    RecreateValidationResponse,
    RepositoryManifest,
    RepositoryRead,
    RepositorySettingsImpactRequest,
    RepositorySettingsImpactResponse,
    RepositorySettingsReadinessResponse,
    RepositorySettingsUpdate,
    RepositoryWithSettings,
)
from private_rag.repositories.service import (
    LocalSettingsReadinessChecker,
    SettingsReadinessChecker,
    analyze_repository_settings_impact,
    check_repository_settings_readiness,
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


def get_settings_chat_llm() -> Generator[ChatLLM, None, None]:
    settings = get_settings()
    yield OllamaChatLLM(base_url=settings.ollama_base_url)


SettingsChatLLMDependency = Annotated[ChatLLM, Depends(get_settings_chat_llm)]


def get_settings_readiness_checker() -> SettingsReadinessChecker:
    return LocalSettingsReadinessChecker()


SettingsReadinessCheckerDependency = Annotated[
    SettingsReadinessChecker, Depends(get_settings_readiness_checker)
]


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


@router.post(
    "/{repository_id}/settings/readiness",
    response_model=RepositorySettingsReadinessResponse,
)
def check_repository_settings_runtime_readiness(
    repository_id: str,
    session: DbSession,
    llm: SettingsChatLLMDependency,
    checker: SettingsReadinessCheckerDependency,
) -> RepositorySettingsReadinessResponse:
    readiness = check_repository_settings_readiness(
        session,
        repository_id=repository_id,
        app_settings=get_settings(),
        llm=llm,
        checker=checker,
    )
    if readiness is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return readiness


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
