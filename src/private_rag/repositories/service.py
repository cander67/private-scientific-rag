from __future__ import annotations

from typing import Literal, Protocol

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from private_rag.chat.llm import ChatLLM
from private_rag.chat.models import ChatMessageRow, ChatSession
from private_rag.core.settings import Settings, get_settings
from private_rag.ingestion.models import Document, DocumentChunk, DocumentVersion
from private_rag.prompt_sandbox.models import SandboxComparison, SandboxRun
from private_rag.repositories.models import Repository, RepositorySettingsRow, RepositorySnapshot
from private_rag.repositories.schemas import (
    RecreateValidationIssue,
    RecreateValidationRequest,
    RecreateValidationResponse,
    RepositoryDashboardActiveConfig,
    RepositoryDashboardActivityItem,
    RepositoryDashboardCounts,
    RepositoryDashboardIndexStatus,
    RepositoryDashboardSummary,
    RepositoryManifest,
    RepositoryRead,
    RepositorySettings,
    RepositorySettingsImpact,
    RepositorySettingsImpactResponse,
    RepositorySettingsReadinessItem,
    RepositorySettingsReadinessResponse,
    RepositoryWithSettings,
    source_file_exists,
)
from private_rag.retrieval.models import RetrievalRun
from private_rag.search.service import FTS_TABLE
from private_rag.vector.embeddings import SentenceTransformersEmbeddingProvider
from private_rag.vector.models import EmbeddingRun

DEFAULT_REPOSITORY_NAME = "Default Repository"
DashboardIndexStatus = Literal["ready", "missing", "partial", "stale"]


class SettingsReadinessChecker(Protocol):
    def check_qdrant(
        self, *, qdrant_url: str, collection_name: str
    ) -> RepositorySettingsReadinessItem:
        """Check vector store connectivity."""

    def check_chat(
        self,
        *,
        llm: ChatLLM,
        model: str,
    ) -> RepositorySettingsReadinessItem:
        """Check configured local chat model readiness."""

    def check_embedding(
        self,
        *,
        provider: str,
        model: str,
        expected_vector_size: int,
    ) -> RepositorySettingsReadinessItem:
        """Check configured embedding model readiness."""

    def check_reranker(
        self,
        *,
        strategy: str,
        model: str | None,
    ) -> RepositorySettingsReadinessItem:
        """Check configured reranker readiness."""


class LocalSettingsReadinessChecker:
    def check_qdrant(
        self, *, qdrant_url: str, collection_name: str
    ) -> RepositorySettingsReadinessItem:
        try:
            response = httpx.get(f"{qdrant_url.rstrip('/')}/collections", timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError:
            return RepositorySettingsReadinessItem(
                target="qdrant",
                label="Qdrant",
                status="unavailable_runtime",
                ready=False,
                message=(
                    "Qdrant is not reachable. Start the configured local Qdrant service "
                    "before rebuilding or searching vectors."
                ),
                model=collection_name,
            )
        return RepositorySettingsReadinessItem(
            target="qdrant",
            label="Qdrant",
            status="ready",
            ready=True,
            message=f"Qdrant responded for configured collection policy '{collection_name}'.",
            model=collection_name,
        )

    def check_chat(
        self,
        *,
        llm: ChatLLM,
        model: str,
    ) -> RepositorySettingsReadinessItem:
        try:
            completion = llm.smoke(model=model)
        except RuntimeError as exc:
            return RepositorySettingsReadinessItem(
                target="chat",
                label="Chat model",
                status="unavailable_runtime",
                ready=False,
                message=_windows_friendly_message(str(exc)),
                model=model,
            )
        return RepositorySettingsReadinessItem(
            target="chat",
            label="Chat model",
            status="ready" if completion.content.strip() else "failed",
            ready=bool(completion.content.strip()),
            message=f"{completion.model} responded to the smoke test.",
            model=completion.model,
        )

    def check_embedding(
        self,
        *,
        provider: str,
        model: str,
        expected_vector_size: int,
    ) -> RepositorySettingsReadinessItem:
        if provider != "sentence_transformers":
            return RepositorySettingsReadinessItem(
                target="embedding",
                label="Embedding model",
                status="skipped",
                ready=False,
                message=(
                    "Embedding smoke checks are currently implemented for SentenceTransformers. "
                    "Verify other providers manually before rebuilding vectors."
                ),
                model=model,
            )
        try:
            embedder = SentenceTransformersEmbeddingProvider(model)
            actual_vector_size = embedder.vector_size
        except RuntimeError as exc:
            return RepositorySettingsReadinessItem(
                target="embedding",
                label="Embedding model",
                status="not_installed",
                ready=False,
                message=_windows_friendly_message(str(exc)),
                model=model,
            )
        if actual_vector_size != expected_vector_size:
            return RepositorySettingsReadinessItem(
                target="embedding",
                label="Embedding model",
                status="failed",
                ready=False,
                message=(
                    f"Embedding model vector size is {actual_vector_size}, but repository "
                    f"settings expect {expected_vector_size}."
                ),
                model=model,
            )
        return RepositorySettingsReadinessItem(
            target="embedding",
            label="Embedding model",
            status="ready",
            ready=True,
            message=f"{model} is cached and reports vector size {actual_vector_size}.",
            model=model,
        )

    def check_reranker(
        self,
        *,
        strategy: str,
        model: str | None,
    ) -> RepositorySettingsReadinessItem:
        if strategy == "none":
            return RepositorySettingsReadinessItem(
                target="reranker",
                label="Reranker",
                status="skipped",
                ready=True,
                message="Reranking is disabled for this repository.",
                model=None,
            )
        if not model:
            return RepositorySettingsReadinessItem(
                target="reranker",
                label="Reranker",
                status="failed",
                ready=False,
                message="Cross-encoder reranking is enabled but no reranker model is configured.",
                model=None,
            )
        try:
            from sentence_transformers import CrossEncoder

            CrossEncoder(model, local_files_only=True)
        except ImportError:
            return RepositorySettingsReadinessItem(
                target="reranker",
                label="Reranker",
                status="unavailable_runtime",
                ready=False,
                message="SentenceTransformers is not installed in the current Python environment.",
                model=model,
            )
        except OSError:
            return RepositorySettingsReadinessItem(
                target="reranker",
                label="Reranker",
                status="not_installed",
                ready=False,
                message=(
                    f"Cross-encoder model '{model}' is not cached locally. Cache it before "
                    "using cross-encoder reranking; PowerShell or terminal commands both work."
                ),
                model=model,
            )
        return RepositorySettingsReadinessItem(
            target="reranker",
            label="Reranker",
            status="ready",
            ready=True,
            message=f"{model} is cached locally for cross-encoder reranking.",
            model=model,
        )


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


def check_repository_settings_readiness(
    session: Session,
    *,
    repository_id: str,
    app_settings: Settings,
    llm: ChatLLM,
    checker: SettingsReadinessChecker,
) -> RepositorySettingsReadinessResponse | None:
    repository_settings = get_repository_with_settings(session, repository_id)
    if repository_settings is None:
        return None
    settings = repository_settings.settings
    items = [
        checker.check_qdrant(
            qdrant_url=app_settings.qdrant_url,
            collection_name=settings.vector.collection_name,
        ),
        checker.check_chat(llm=llm, model=settings.model.ollama_chat_model),
        checker.check_embedding(
            provider=settings.embedding.provider,
            model=settings.embedding.model,
            expected_vector_size=settings.vector.vector_size,
        ),
        checker.check_reranker(
            strategy=settings.reranking.strategy,
            model=settings.reranking.model,
        ),
    ]
    return RepositorySettingsReadinessResponse(
        repository_id=repository_id,
        checked=True,
        items=items,
    )


def repository_dashboard_summary(
    session: Session,
    *,
    repository_id: str,
    app_settings: Settings,
    llm: ChatLLM,
    checker: SettingsReadinessChecker,
) -> RepositoryDashboardSummary | None:
    repository_settings = get_repository_with_settings(session, repository_id)
    if repository_settings is None:
        return None
    settings = repository_settings.settings
    parsed_chunks = _count(
        session,
        DocumentChunk,
        DocumentChunk.repository_id == repository_id,
    )
    full_text_count = _full_text_count(session, repository_id)
    embedding_run = session.scalar(
        select(EmbeddingRun).where(EmbeddingRun.repository_id == repository_id)
    )
    vector_count = embedding_run.chunk_count if embedding_run is not None else 0
    full_text_status, full_text_ready = _index_readiness_status(
        parsed_chunks=parsed_chunks,
        indexed_chunks=full_text_count,
    )
    vector_status, vector_ready = _index_readiness_status(
        parsed_chunks=parsed_chunks,
        indexed_chunks=vector_count,
        index_state=embedding_run.status if embedding_run is not None else None,
    )
    readiness = check_repository_settings_readiness(
        session,
        repository_id=repository_id,
        app_settings=app_settings,
        llm=llm,
        checker=checker,
    )
    if readiness is None:
        return None

    warnings = _summary_warnings(
        full_text_status=full_text_status,
        vector_status=vector_status,
        readiness=readiness,
    )
    return RepositoryDashboardSummary(
        repository=repository_settings.repository,
        counts=RepositoryDashboardCounts(
            documents=_count(session, Document, Document.repository_id == repository_id),
            parsed_documents=_count(
                session,
                DocumentVersion,
                DocumentVersion.repository_id == repository_id,
                DocumentVersion.status == "parsed",
            ),
            chunks=parsed_chunks,
            chat_sessions=_count(
                session,
                ChatSession,
                ChatSession.repository_id == repository_id,
            ),
            chat_messages=_count(
                session,
                ChatMessageRow,
                ChatMessageRow.repository_id == repository_id,
            ),
            retrieval_runs=_count(
                session,
                RetrievalRun,
                RetrievalRun.repository_id == repository_id,
            ),
            sandbox_runs=_count(session, SandboxRun, SandboxRun.repository_id == repository_id),
            sandbox_comparisons=_count(
                session,
                SandboxComparison,
                SandboxComparison.repository_id == repository_id,
            ),
        ),
        full_text=RepositoryDashboardIndexStatus(
            ready=full_text_ready,
            status=full_text_status,
            message=_full_text_readiness_message(parsed_chunks, full_text_count),
            indexed_chunks=full_text_count,
            parsed_chunks=parsed_chunks,
        ),
        vector=RepositoryDashboardIndexStatus(
            ready=vector_ready,
            status=vector_status,
            message=_vector_readiness_message(parsed_chunks, embedding_run),
            indexed_chunks=vector_count,
            parsed_chunks=parsed_chunks,
            model=embedding_run.model if embedding_run is not None else None,
        ),
        settings_readiness=readiness,
        active_config=RepositoryDashboardActiveConfig(
            chunking=settings.chunking,
            full_text=settings.full_text,
            vector=settings.vector,
            embedding=settings.embedding,
            reranking=settings.reranking,
            chat_model=settings.model.ollama_chat_model,
            active_chat_prompt_id=settings.prompt.active_chat_prompt_id,
            active_chat_prompt_name=settings.prompt.active_chat_prompt.name,
        ),
        recent_activity=_recent_activity(session, repository_id=repository_id),
        warnings=warnings,
    )


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


def _windows_friendly_message(message: str) -> str:
    return (
        message.replace("Start Ollama and run `", "Start Ollama, then pull the model with: ")
        .replace("`.", ".")
        .replace("`", "")
    )


def _count(session: Session, model: type[object], *criteria: ColumnElement[bool]) -> int:
    value = session.scalar(select(func.count()).select_from(model).where(*criteria))
    return int(value or 0)


def _full_text_count(session: Session, repository_id: str) -> int:
    try:
        value = session.scalar(
            text(f"SELECT COUNT(*) FROM {FTS_TABLE} WHERE repository_id = :repository_id"),
            {"repository_id": repository_id},
        )
    except Exception:
        session.rollback()
        return 0
    return int(value or 0)


def _index_readiness_status(
    *,
    parsed_chunks: int,
    indexed_chunks: int,
    index_state: str | None = "indexed",
) -> tuple[DashboardIndexStatus, bool]:
    if parsed_chunks == 0 or indexed_chunks == 0 or index_state != "indexed":
        return "missing", False
    if indexed_chunks < parsed_chunks:
        return "partial", False
    if indexed_chunks > parsed_chunks:
        return "stale", False
    return "ready", True


def _full_text_readiness_message(parsed_chunks: int, indexed_chunks: int) -> str:
    if parsed_chunks == 0:
        return "No parsed chunks are available to index"
    if indexed_chunks == 0:
        return "Full-text index has not been rebuilt"
    if indexed_chunks < parsed_chunks:
        return f"{indexed_chunks} of {parsed_chunks} full-text chunks indexed"
    if indexed_chunks > parsed_chunks:
        return (
            f"{indexed_chunks} full-text chunks indexed for {parsed_chunks} parsed chunks; "
            "rebuild recommended"
        )
    return f"{indexed_chunks} of {parsed_chunks} full-text chunks indexed"


def _vector_readiness_message(parsed_chunks: int, embedding_run: EmbeddingRun | None) -> str:
    if parsed_chunks == 0:
        return "No parsed chunks are available to embed/index"
    if embedding_run is None:
        return "Vector index has not been rebuilt"
    if embedding_run.status != "indexed":
        return f"Vector index status is {embedding_run.status}"
    if embedding_run.chunk_count == 0:
        return "Vector index exists but contains zero chunks"
    if embedding_run.chunk_count < parsed_chunks:
        return f"{embedding_run.chunk_count} of {parsed_chunks} vector chunks indexed"
    if embedding_run.chunk_count > parsed_chunks:
        return (
            f"{embedding_run.chunk_count} vector chunks indexed for {parsed_chunks} parsed "
            "chunks; rebuild recommended"
        )
    return f"{embedding_run.chunk_count} of {parsed_chunks} vector chunks indexed"


def _summary_warnings(
    *,
    full_text_status: str,
    vector_status: str,
    readiness: RepositorySettingsReadinessResponse,
) -> list[str]:
    warnings: list[str] = []
    if full_text_status in {"missing", "partial", "stale"}:
        warnings.append("Full-text index needs attention before search and chat are fully ready.")
    if vector_status in {"missing", "partial", "stale"}:
        warnings.append("Vector index needs attention before semantic retrieval is fully ready.")
    for item in readiness.items:
        if not item.ready:
            warnings.append(item.message)
    return warnings


def _recent_activity(
    session: Session,
    *,
    repository_id: str,
    limit: int = 8,
) -> list[RepositoryDashboardActivityItem]:
    repository = session.get(Repository, repository_id)
    items: list[RepositoryDashboardActivityItem] = []
    if repository is not None:
        items.append(
            RepositoryDashboardActivityItem(
                kind="recreate",
                label=repository.name,
                detail="Repository created or restored",
                occurred_at=repository.created_at,
                route="recreate",
            )
        )

    documents = session.scalars(
        select(Document)
        .where(Document.repository_id == repository_id)
        .order_by(Document.updated_at.desc(), Document.created_at.desc(), Document.id.desc())
        .limit(limit)
    ).all()
    items.extend(
        RepositoryDashboardActivityItem(
            kind="document",
            label=document.display_name,
            detail="Document uploaded or updated",
            occurred_at=document.updated_at,
            route="documents",
        )
        for document in documents
    )

    chat_sessions = session.scalars(
        select(ChatSession)
        .where(ChatSession.repository_id == repository_id)
        .order_by(
            ChatSession.updated_at.desc(), ChatSession.created_at.desc(), ChatSession.id.desc()
        )
        .limit(limit)
    ).all()
    items.extend(
        RepositoryDashboardActivityItem(
            kind="chat",
            label=chat_session.title,
            detail=f"{chat_session.model} chat session",
            occurred_at=chat_session.updated_at,
            route="chat",
        )
        for chat_session in chat_sessions
    )

    retrieval_runs = session.scalars(
        select(RetrievalRun)
        .where(RetrievalRun.repository_id == repository_id)
        .order_by(RetrievalRun.created_at.desc(), RetrievalRun.id.desc())
        .limit(limit)
    ).all()
    items.extend(
        RepositoryDashboardActivityItem(
            kind="retrieval",
            label=run.query,
            detail=f"{run.mode} retrieval run",
            occurred_at=run.created_at,
            route="search",
        )
        for run in retrieval_runs
    )

    sandbox_runs = session.scalars(
        select(SandboxRun)
        .where(SandboxRun.repository_id == repository_id)
        .order_by(SandboxRun.created_at.desc(), SandboxRun.id.desc())
        .limit(limit)
    ).all()
    items.extend(
        RepositoryDashboardActivityItem(
            kind="sandbox",
            label=run.label or run.query,
            detail=f"{run.status} sandbox run",
            occurred_at=run.created_at,
            route="sandbox",
        )
        for run in sandbox_runs
    )

    snapshots = session.scalars(
        select(RepositorySnapshot)
        .where(RepositorySnapshot.repository_id == repository_id)
        .order_by(RepositorySnapshot.created_at.desc(), RepositorySnapshot.id.desc())
        .limit(limit)
    ).all()
    items.extend(
        RepositoryDashboardActivityItem(
            kind="export",
            label="Repository manifest",
            detail="Export or settings snapshot recorded",
            occurred_at=snapshot.created_at,
            route="export",
        )
        for snapshot in snapshots
    )

    return sorted(items, key=lambda item: item.occurred_at, reverse=True)[:limit]


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
