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
    RepositorySettingsImpact,
    RepositorySettingsImpactResponse,
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


def list_repositories(session: Session) -> list[RepositoryRead]:
    repositories = session.scalars(select(Repository).order_by(Repository.created_at)).all()
    return [
        RepositoryRead(
            id=repository.id,
            name=repository.name,
            root_path=repository.root_path,
            created_at=repository.created_at,
            updated_at=repository.updated_at,
        )
        for repository in repositories
    ]


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
    session.flush()
    session.add(
        RepositorySnapshot(
            repository_id=repository_id,
            manifest=_manifest_for_repository(repository, settings),
        )
    )
    session.commit()
    session.refresh(repository)
    return _with_settings(repository)


def analyze_repository_settings_impact(
    session: Session,
    repository_id: str,
    draft_settings: RepositorySettings,
) -> RepositorySettingsImpactResponse | None:
    repository_settings = get_repository_with_settings(session, repository_id)
    if repository_settings is None:
        return None
    return analyze_settings_impact(repository_settings.settings, draft_settings)


def analyze_settings_impact(
    current_settings: RepositorySettings,
    draft_settings: RepositorySettings,
) -> RepositorySettingsImpactResponse:
    current = current_settings.model_dump(mode="json")
    draft = draft_settings.model_dump(mode="json")
    impacts: list[RepositorySettingsImpact] = []

    def changed(*fields: str) -> list[str]:
        return [
            field for field in fields if _field_value(current, field) != _field_value(draft, field)
        ]

    parsing_fields = changed(
        "chunking.mode",
        "chunking.chunk_size",
        "chunking.chunk_overlap",
        "parser.structured_parser",
        "parser.fallback_parser",
    )
    if parsing_fields:
        impacts.append(
            RepositorySettingsImpact(
                category="document_reprocessing",
                title="Document reprocessing required",
                message=(
                    "Chunking or parser defaults changed. Existing parsed documents and chunks "
                    "will not match these defaults until documents are reprocessed."
                ),
                fields=parsing_fields,
                actions=["Reprocess affected documents in Document Manager."],
            )
        )

    full_text_fields = changed(
        "full_text.tokenizer",
        "full_text.prefix_index",
        "full_text.porter_stemming",
    )
    if full_text_fields or parsing_fields:
        impacts.append(
            RepositorySettingsImpact(
                category="full_text_rebuild",
                title="Full-text index rebuild required",
                message=(
                    "Full-text search readiness is stale until the sparse index is rebuilt "
                    "with the saved defaults."
                ),
                fields=[*parsing_fields, *full_text_fields],
                actions=["Rebuild full-text search from Search Lab or Chat Workspace."],
            )
        )

    vector_fields = changed(
        "embedding.provider",
        "embedding.model",
        "vector.collection_name",
        "vector.vector_size",
        "vector.distance",
    )
    if vector_fields or parsing_fields:
        impacts.append(
            RepositorySettingsImpact(
                category="vector_rebuild",
                title="Vector index rebuild required",
                message=(
                    "Semantic and hybrid retrieval readiness is stale until embeddings and "
                    "the vector collection are rebuilt with the saved defaults."
                ),
                fields=[*parsing_fields, *vector_fields],
                actions=[
                    "Rebuild the vector index before relying on semantic or hybrid retrieval."
                ],
            )
        )

    retrieval_fields = changed("reranking.strategy", "reranking.model")
    if retrieval_fields:
        impacts.append(
            RepositorySettingsImpact(
                category="retrieval_defaults",
                title="Retrieval defaults changed",
                message=(
                    "Reranking defaults changed. New Search Lab, Chat Workspace, and Prompt "
                    "Sandbox runs should be reviewed against the new retrieval behavior."
                ),
                fields=retrieval_fields,
                actions=["Revisit retrieval defaults in Search Lab and rerun important checks."],
            )
        )

    chat_fields = changed("model.ollama_chat_model")
    if chat_fields or retrieval_fields:
        impacts.append(
            RepositorySettingsImpact(
                category="chat_defaults",
                title="Chat defaults changed",
                message=(
                    "New Chat Workspace sessions will use different model or retrieval defaults. "
                    "Existing sessions keep their persisted run settings."
                ),
                fields=[*chat_fields, *retrieval_fields],
                actions=["Start a new chat session to verify the saved defaults."],
            )
        )

    prompt_fields = changed("prompt.version", "prompt.active_chat_prompt_id", "prompt.library")
    if prompt_fields:
        impacts.append(
            RepositorySettingsImpact(
                category="prompt_defaults",
                title="Prompt defaults changed",
                message=(
                    "Normal chat prompt defaults changed. Prompt Sandbox versions remain isolated "
                    "from these chat defaults."
                ),
                fields=prompt_fields,
                actions=["Verify the active prompt before starting new chat sessions."],
            )
        )

    export_fields = changed("export.include_sources", "export.include_indexes", "export.format")
    compatibility_fields = [
        *parsing_fields,
        *full_text_fields,
        *vector_fields,
        *retrieval_fields,
        *chat_fields,
        *prompt_fields,
        *export_fields,
    ]
    if compatibility_fields:
        impacts.append(
            RepositorySettingsImpact(
                category="export_recreate",
                severity="info",
                title="Export and recreate metadata will change",
                message=(
                    "Future portable bundles and recreate validation will include these saved "
                    "defaults. Older exports keep the settings captured when they were created."
                ),
                fields=compatibility_fields,
                actions=["Create a fresh export after saving if this configuration should travel."],
            )
        )

    if [
        *parsing_fields,
        *full_text_fields,
        *vector_fields,
        *retrieval_fields,
        *chat_fields,
        *prompt_fields,
    ]:
        impacts.append(
            RepositorySettingsImpact(
                category="evaluation_freshness",
                severity="info",
                title="Evaluation evidence may be stale",
                message=(
                    "Retrieval or generation defaults changed. Any prior manual checks or golden "
                    "evaluation notes should be rerun before promoting these defaults."
                ),
                fields=[
                    *parsing_fields,
                    *full_text_fields,
                    *vector_fields,
                    *retrieval_fields,
                    *chat_fields,
                    *prompt_fields,
                ],
                actions=["Rerun relevant searches, chats, or sandbox comparisons."],
            )
        )

    return RepositorySettingsImpactResponse(has_changes=current != draft, impacts=impacts)


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


def _field_value(payload: dict[str, object], dotted_path: str) -> object:
    value: object = payload
    for part in dotted_path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _manifest_for_repository(
    repository: Repository,
    settings: RepositorySettings,
) -> dict[str, object]:
    return RepositoryManifest(
        repository=RepositoryRead(
            id=repository.id,
            name=repository.name,
            root_path=repository.root_path,
            created_at=repository.created_at,
            updated_at=repository.updated_at,
        ),
        settings=settings,
        source_files=[],
    ).model_dump(mode="json")


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
