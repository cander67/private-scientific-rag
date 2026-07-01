from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from private_rag.core.settings import Settings, get_settings
from private_rag.ingestion.models import DocumentVersion
from private_rag.repositories.models import Repository, RepositorySettingsRow, RepositorySnapshot
from private_rag.repositories.schemas import (
    RecreateValidationIssue,
    RecreateValidationRequest,
    RecreateValidationResponse,
    RepositoryManifest,
    RepositoryRead,
    RepositorySettings,
    RepositoryWithSettings,
    source_file_exists,
)

DEFAULT_REPOSITORY_NAME = "Default Repository"


def ensure_default_repository(
    session: Session,
    settings: Settings | None = None,
) -> RepositoryWithSettings:
    app_settings = settings or get_settings()
    repository = session.scalar(
        select(Repository).where(Repository.name == DEFAULT_REPOSITORY_NAME)
    )
    if repository is None:
        repository = Repository(name=DEFAULT_REPOSITORY_NAME, root_path=str(app_settings.data_dir))
        session.add(repository)
        session.flush()

    if repository.settings is None:
        default_settings = RepositorySettings.from_app_settings(app_settings)
        repository.settings = RepositorySettingsRow(
            settings=default_settings.model_dump(mode="json"),
        )
        session.add(repository.settings)
        session.flush()

    session.commit()
    session.refresh(repository)
    return _with_settings(repository)


def get_repository_with_settings(
    session: Session, repository_id: str
) -> RepositoryWithSettings | None:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    return _with_settings(repository)


def update_repository_settings(
    session: Session,
    repository_id: str,
    settings: RepositorySettings,
) -> RepositoryWithSettings | None:
    repository = session.get(Repository, repository_id)
    if repository is None:
        return None
    if repository.settings is None:
        repository.settings = RepositorySettingsRow(settings=settings.model_dump(mode="json"))
    else:
        repository.settings.settings = settings.model_dump(mode="json")
    session.add(repository)
    session.commit()
    session.refresh(repository)
    return _with_settings(repository)


def export_manifest(session: Session, repository_id: str) -> RepositoryManifest | None:
    repository_settings = get_repository_with_settings(session, repository_id)
    if repository_settings is None:
        return None
    manifest = RepositoryManifest(
        repository=repository_settings.repository,
        settings=repository_settings.settings,
        source_files=list_source_files(session, repository_id),
    )
    snapshot = RepositorySnapshot(
        repository_id=repository_id,
        manifest=manifest.model_dump(mode="json"),
    )
    session.add(snapshot)
    session.commit()
    return manifest


def validate_recreate_request(request: RecreateValidationRequest) -> RecreateValidationResponse:
    missing_source_files = [
        RecreateValidationIssue(
            code="missing_source_file",
            message=f"Source file is not available: {path}",
            path=path,
        )
        for path in request.manifest.source_files
        if not source_file_exists(path)
    ]

    required_models = [
        request.manifest.settings.embedding.model,
        request.manifest.settings.model.ollama_chat_model,
    ]
    if request.manifest.settings.reranking.strategy != "none":
        reranker = request.manifest.settings.reranking.model
        if reranker is not None:
            required_models.append(reranker)

    available_models = set(request.available_models)
    missing_models = [
        RecreateValidationIssue(
            code="missing_model",
            message=f"Required model is not available: {model}",
            setting="model",
        )
        for model in required_models
        if available_models and model not in available_models
    ]

    incompatible_settings: list[RecreateValidationIssue] = []
    if (
        request.manifest.settings.vector.distance == "dot"
        and request.manifest.settings.embedding.provider == "ollama"
    ):
        incompatible_settings.append(
            RecreateValidationIssue(
                code="incompatible_vector_distance",
                message="Ollama embeddings currently require cosine distance.",
                setting="vector.distance",
            )
        )

    return RecreateValidationResponse(
        can_recreate=not missing_source_files and not missing_models and not incompatible_settings,
        missing_source_files=missing_source_files,
        missing_models=missing_models,
        incompatible_settings=incompatible_settings,
    )


def list_source_files(session: Session, repository_id: str) -> list[str]:
    return list(
        session.scalars(
            select(DocumentVersion.storage_path)
            .where(DocumentVersion.repository_id == repository_id)
            .order_by(DocumentVersion.created_at)
        )
    )


def _with_settings(repository: Repository) -> RepositoryWithSettings:
    if repository.settings is None:
        raise ValueError("Repository settings have not been initialized")
    return RepositoryWithSettings(
        repository=RepositoryRead(
            id=repository.id,
            name=repository.name,
            root_path=repository.root_path,
            created_at=repository.created_at,
            updated_at=repository.updated_at,
        ),
        settings=RepositorySettings.model_validate(repository.settings.settings),
    )
