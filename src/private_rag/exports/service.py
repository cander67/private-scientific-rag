from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from private_rag.chat.models import ChatMessageRow, ChatSession
from private_rag.exports.schemas import (
    ExportBundleBuildResult,
    ExportBundleManifest,
    ExportBundleOptions,
    ExportBundleSource,
    ExportBundleSourceMapping,
    ExportBundleValidationIssue,
    ExportBundleValidationResponse,
)
from private_rag.ingestion.models import Document, DocumentChunk, DocumentVersion
from private_rag.prompt_sandbox.models import (
    SandboxComparison,
    SandboxPromptVersion,
    SandboxRun,
)
from private_rag.repositories.service import get_repository_with_settings
from private_rag.retrieval.models import RetrievalResult, RetrievalRun

MANIFEST_PATH = "manifest.json"
SETTINGS_PAYLOAD_PATH = "payloads/settings.json"
PROMPTS_PAYLOAD_PATH = "payloads/prompts.json"
DOCUMENTS_PAYLOAD_PATH = "payloads/documents.json"
CHUNKS_PAYLOAD_PATH = "payloads/chunks.json"
CHAT_PAYLOAD_PATH = "payloads/chat.json"
RETRIEVAL_PAYLOAD_PATH = "payloads/retrieval.json"
SANDBOX_PAYLOAD_PATH = "payloads/sandbox.json"


def build_export_bundle(
    session: Session,
    repository_id: str,
    options: ExportBundleOptions | None = None,
) -> ExportBundleBuildResult | None:
    repository_with_settings = get_repository_with_settings(session, repository_id)
    if repository_with_settings is None:
        return None

    settings = repository_with_settings.settings
    requested_options = options or ExportBundleOptions()
    include_sources = (
        settings.export.include_sources
        if requested_options.include_sources is None
        else requested_options.include_sources
    )

    payloads: dict[str, str] = {
        "settings": SETTINGS_PAYLOAD_PATH,
        "prompts": PROMPTS_PAYLOAD_PATH,
        "documents": DOCUMENTS_PAYLOAD_PATH,
        "chunks": CHUNKS_PAYLOAD_PATH,
        "chat": CHAT_PAYLOAD_PATH,
        "retrieval": RETRIEVAL_PAYLOAD_PATH,
    }
    if requested_options.include_sandbox:
        payloads["sandbox"] = SANDBOX_PAYLOAD_PATH

    documents = _documents_payload(session, repository_id)
    chunks = _chunks_payload(session, repository_id)
    chat = _chat_payload(session, repository_id)
    retrieval = _retrieval_payload(session, repository_id)
    sandbox = (
        _sandbox_payload(session, repository_id) if requested_options.include_sandbox else None
    )

    source_rows = session.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.repository_id == repository_id)
        .order_by(DocumentVersion.created_at, DocumentVersion.id)
    ).all()
    sources, source_bytes, source_warnings = _source_entries(source_rows, include_sources)

    prompt_settings = settings.prompt.model_dump(mode="json")
    manifest = ExportBundleManifest(
        generated_at=datetime.now(UTC).isoformat(),
        repository=repository_with_settings.repository.model_dump(mode="json"),
        export_options={
            "include_sources": include_sources,
            "include_sandbox": requested_options.include_sandbox,
            "format": settings.export.format,
        },
        settings=settings.model_dump(mode="json"),
        required_models=_required_models(settings.model_dump(mode="json")),
        payloads=payloads,
        sources=sources,
        counts={
            "sources": len(sources),
            "included_sources": sum(1 for source in sources if source.included),
            "documents": len(documents["documents"]),
            "document_versions": len(documents["versions"]),
            "chunks": len(chunks["chunks"]),
            "chat_sessions": len(chat["sessions"]),
            "chat_messages": len(chat["messages"]),
            "chat_citations": sum(len(message["citations"]) for message in chat["messages"]),
            "retrieval_runs": len(retrieval["runs"]),
            "retrieval_results": len(retrieval["results"]),
            "sandbox_prompt_versions": len(sandbox["prompt_versions"]) if sandbox else 0,
            "sandbox_runs": len(sandbox["runs"]) if sandbox else 0,
            "sandbox_comparisons": len(sandbox["comparisons"]) if sandbox else 0,
        },
        warnings=source_warnings,
    )

    zip_data = _build_zip(
        {
            MANIFEST_PATH: manifest.model_dump(mode="json"),
            SETTINGS_PAYLOAD_PATH: {
                "repository": repository_with_settings.repository.model_dump(mode="json"),
                "settings": settings.model_dump(mode="json"),
            },
            PROMPTS_PAYLOAD_PATH: {
                "prompt": prompt_settings,
            },
            DOCUMENTS_PAYLOAD_PATH: documents,
            CHUNKS_PAYLOAD_PATH: chunks,
            CHAT_PAYLOAD_PATH: chat,
            RETRIEVAL_PAYLOAD_PATH: retrieval,
            **({SANDBOX_PAYLOAD_PATH: sandbox} if sandbox is not None else {}),
        },
        source_bytes,
    )
    return ExportBundleBuildResult(
        filename=_bundle_filename(str(repository_with_settings.repository.name)),
        data=zip_data,
        manifest=manifest,
    )


def validate_export_bundle_data(
    data: bytes,
    available_models: Sequence[str] | None = None,
    source_mappings: Sequence[ExportBundleSourceMapping] | None = None,
) -> ExportBundleValidationResponse:
    try:
        with ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            if MANIFEST_PATH not in names:
                return _validation_response(
                    errors=[
                        _issue(
                            "error",
                            "missing_manifest",
                            "Export bundle is missing manifest.json.",
                            path=MANIFEST_PATH,
                        )
                    ]
                )

            try:
                manifest_payload = json.loads(archive.read(MANIFEST_PATH))
            except json.JSONDecodeError as exc:
                return _validation_response(
                    errors=[
                        _issue(
                            "error",
                            "invalid_manifest_json",
                            f"manifest.json is not valid JSON: {exc.msg}.",
                            path=MANIFEST_PATH,
                        )
                    ]
                )

            unsupported_schema_issue = _unsupported_schema_issue(manifest_payload)
            if unsupported_schema_issue is not None:
                return _validation_response(errors=[unsupported_schema_issue])

            try:
                manifest = ExportBundleManifest.model_validate(manifest_payload)
            except ValidationError as exc:
                return _validation_response(
                    errors=[
                        _issue(
                            "error",
                            "invalid_manifest_schema",
                            f"manifest.json does not match the export bundle schema: {exc.errors()[0]['msg']}.",
                            path=MANIFEST_PATH,
                        )
                    ]
                )

            errors: list[ExportBundleValidationIssue] = []
            warnings: list[ExportBundleValidationIssue] = []
            informational: list[ExportBundleValidationIssue] = []
            payloads = _read_payloads(archive, manifest, names, errors)
            _validate_source_entries(
                archive=archive,
                names=names,
                manifest=manifest,
                source_mappings=source_mappings or [],
                errors=errors,
                warnings=warnings,
                informational=informational,
            )
            _validate_models(
                manifest=manifest,
                available_models=available_models,
                warnings=warnings,
                informational=informational,
            )
            _validate_counts(manifest, payloads, errors)
            _report_parser_fingerprints(payloads, informational)

            return ExportBundleValidationResponse(
                can_recreate=not errors,
                manifest=manifest,
                counts=dict(manifest.counts),
                required_models=list(manifest.required_models),
                blocking_errors=errors,
                warnings=warnings,
                informational=informational,
            )
    except BadZipFile:
        return _validation_response(
            errors=[
                _issue(
                    "error",
                    "invalid_zip",
                    "Export bundle is not a valid ZIP file.",
                )
            ]
        )


def source_bundle_path(sha256: str, filename: str) -> str:
    return f"sources/{sha256}/{_safe_filename(filename)}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_entries(
    versions: Sequence[DocumentVersion],
    include_sources: bool,
) -> tuple[list[ExportBundleSource], dict[str, bytes], list[str]]:
    entries: list[ExportBundleSource] = []
    source_bytes: dict[str, bytes] = {}
    warnings: list[str] = []

    for version in versions:
        source_path = Path(version.storage_path)
        exists = source_path.exists()
        actual_sha256 = sha256_file(source_path) if exists else version.sha256
        bundle_path = (
            source_bundle_path(actual_sha256, version.original_filename)
            if include_sources and exists
            else None
        )
        if include_sources and exists and bundle_path is not None:
            source_bytes[bundle_path] = source_path.read_bytes()
        if include_sources and not exists:
            warnings.append(f"Source file is missing and was not included: {version.storage_path}")

        entries.append(
            ExportBundleSource(
                document_id=version.document_id,
                document_version_id=version.id,
                original_filename=version.original_filename,
                content_type=version.content_type,
                source_type=version.source_type,
                sha256=actual_sha256,
                byte_size=version.byte_size,
                original_storage_path=version.storage_path,
                bundle_path=bundle_path,
                included=bundle_path is not None,
                missing=not exists,
            )
        )

    return entries, source_bytes, warnings


def _documents_payload(session: Session, repository_id: str) -> dict[str, list[dict[str, Any]]]:
    documents = session.scalars(
        select(Document)
        .where(Document.repository_id == repository_id)
        .order_by(Document.created_at, Document.id)
    ).all()
    versions = session.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.repository_id == repository_id)
        .order_by(DocumentVersion.created_at, DocumentVersion.id)
    ).all()
    return {
        "documents": [
            {
                "id": document.id,
                "repository_id": document.repository_id,
                "display_name": document.display_name,
                "current_version_id": document.current_version_id,
                "created_at": _serialize_value(document.created_at),
                "updated_at": _serialize_value(document.updated_at),
            }
            for document in documents
        ],
        "versions": [
            {
                "id": version.id,
                "document_id": version.document_id,
                "repository_id": version.repository_id,
                "original_filename": version.original_filename,
                "content_type": version.content_type,
                "source_type": version.source_type,
                "sha256": version.sha256,
                "byte_size": version.byte_size,
                "storage_path": version.storage_path,
                "status": version.status,
                "parser_name": version.parser_name,
                "parser_version": version.parser_version,
                "ocr_required": version.ocr_required,
                "page_count": version.page_count,
                "line_count": version.line_count,
                "section_count": version.section_count,
                "chunk_count": version.chunk_count,
                "warnings": version.warnings,
                "metadata": version.extra_metadata,
                "created_at": _serialize_value(version.created_at),
                "updated_at": _serialize_value(version.updated_at),
            }
            for version in versions
        ],
    }


def _chunks_payload(session: Session, repository_id: str) -> dict[str, list[dict[str, Any]]]:
    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.repository_id == repository_id)
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index, DocumentChunk.id)
    ).all()
    return {
        "chunks": [
            {
                "id": chunk.id,
                "repository_id": chunk.repository_id,
                "document_id": chunk.document_id,
                "document_version_id": chunk.document_version_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "section": chunk.section,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "parser_version": chunk.parser_version,
                "metadata": chunk.extra_metadata,
                "created_at": _serialize_value(chunk.created_at),
            }
            for chunk in chunks
        ]
    }


def _chat_payload(session: Session, repository_id: str) -> dict[str, list[dict[str, Any]]]:
    sessions = session.scalars(
        select(ChatSession)
        .where(ChatSession.repository_id == repository_id)
        .order_by(ChatSession.created_at, ChatSession.id)
    ).all()
    messages = session.scalars(
        select(ChatMessageRow)
        .where(ChatMessageRow.repository_id == repository_id)
        .order_by(ChatMessageRow.session_id, ChatMessageRow.sequence, ChatMessageRow.id)
    ).all()
    return {
        "sessions": [
            {
                "id": chat_session.id,
                "repository_id": chat_session.repository_id,
                "title": chat_session.title,
                "model": chat_session.model,
                "retrieval_settings": chat_session.retrieval_settings,
                "prompt_id": chat_session.prompt_id,
                "created_at": _serialize_value(chat_session.created_at),
                "updated_at": _serialize_value(chat_session.updated_at),
            }
            for chat_session in sessions
        ],
        "messages": [
            {
                "id": message.id,
                "session_id": message.session_id,
                "repository_id": message.repository_id,
                "sequence": message.sequence,
                "role": message.role,
                "content": message.content,
                "retrieval_run_id": message.retrieval_run_id,
                "citations": message.citations,
                "metadata": message.extra_metadata,
                "created_at": _serialize_value(message.created_at),
            }
            for message in messages
        ],
    }


def _retrieval_payload(session: Session, repository_id: str) -> dict[str, list[dict[str, Any]]]:
    runs = session.scalars(
        select(RetrievalRun)
        .where(RetrievalRun.repository_id == repository_id)
        .order_by(RetrievalRun.created_at, RetrievalRun.id)
    ).all()
    results = session.scalars(
        select(RetrievalResult)
        .where(RetrievalResult.repository_id == repository_id)
        .order_by(RetrievalResult.run_id, RetrievalResult.rank, RetrievalResult.id)
    ).all()
    return {
        "runs": [
            {
                "id": run.id,
                "repository_id": run.repository_id,
                "mode": run.mode,
                "query": run.query,
                "filters": run.filters,
                "top_k": run.top_k,
                "candidate_pool_size": run.candidate_pool_size,
                "rrf_constant": run.rrf_constant,
                "embedding_model": run.embedding_model,
                "embedding_run_id": run.embedding_run_id,
                "vector_collection_name": run.vector_collection_name,
                "reranker_strategy": run.reranker_strategy,
                "reranker_model": run.reranker_model,
                "metadata_boosts": run.metadata_boosts,
                "settings_snapshot": run.settings_snapshot,
                "created_at": _serialize_value(run.created_at),
            }
            for run in runs
        ],
        "results": [
            {
                "id": result.id,
                "run_id": result.run_id,
                "repository_id": result.repository_id,
                "document_id": result.document_id,
                "document_version_id": result.document_version_id,
                "chunk_id": result.chunk_id,
                "chunk_index": result.chunk_index,
                "rank": result.rank,
                "final_score": result.final_score,
                "score_breakdown": result.score_breakdown,
                "source_ranks": result.source_ranks,
                "matched_fields": result.matched_fields,
                "metadata": result.result_metadata,
                "created_at": _serialize_value(result.created_at),
            }
            for result in results
        ],
    }


def _sandbox_payload(session: Session, repository_id: str) -> dict[str, list[dict[str, Any]]]:
    prompt_versions = session.scalars(
        select(SandboxPromptVersion)
        .where(SandboxPromptVersion.repository_id == repository_id)
        .order_by(SandboxPromptVersion.created_at, SandboxPromptVersion.id)
    ).all()
    runs = session.scalars(
        select(SandboxRun)
        .where(SandboxRun.repository_id == repository_id)
        .order_by(SandboxRun.created_at, SandboxRun.id)
    ).all()
    comparisons = session.scalars(
        select(SandboxComparison)
        .where(SandboxComparison.repository_id == repository_id)
        .order_by(SandboxComparison.created_at, SandboxComparison.id)
    ).all()
    return {
        "prompt_versions": [
            {
                "id": item.id,
                "repository_id": item.repository_id,
                "name": item.name,
                "body": item.body,
                "notes": item.notes,
                "source_chat_prompt_id": item.source_chat_prompt_id,
                "used_by_run": item.used_by_run,
                "created_at": _serialize_value(item.created_at),
            }
            for item in prompt_versions
        ],
        "runs": [
            {
                "id": item.id,
                "repository_id": item.repository_id,
                "prompt_version_id": item.prompt_version_id,
                "comparison_id": item.comparison_id,
                "comparison_index": item.comparison_index,
                "label": item.label,
                "query": item.query,
                "model": item.model,
                "retrieval_settings": item.retrieval_settings,
                "prompt_snapshot": item.prompt_snapshot,
                "context_entries": item.context_entries,
                "retrieval_run_id": item.retrieval_run_id,
                "answer": item.answer,
                "citations": item.citations,
                "metrics": item.metrics,
                "latency_ms": item.latency_ms,
                "status": item.status,
                "created_at": _serialize_value(item.created_at),
            }
            for item in runs
        ],
        "comparisons": [
            {
                "id": item.id,
                "repository_id": item.repository_id,
                "query": item.query,
                "status": item.status,
                "expected_run_count": item.expected_run_count,
                "created_at": _serialize_value(item.created_at),
            }
            for item in comparisons
        ],
    }


def _required_models(settings: dict[str, Any]) -> list[str]:
    models = [
        str(settings["embedding"]["model"]),
        str(settings["model"]["ollama_chat_model"]),
    ]
    reranking = settings["reranking"]
    reranker_model = reranking.get("model") if isinstance(reranking, dict) else None
    if reranking.get("strategy") != "none" and reranker_model:
        models.append(str(reranker_model))
    return sorted(set(models))


def _build_zip(payloads: dict[str, Any], source_bytes: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(payloads):
            archive.writestr(path, _json_bytes(payloads[path]))
        for path in sorted(source_bytes):
            archive.writestr(path, source_bytes[path])
    return buffer.getvalue()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "source"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def _bundle_filename(repository_name: str) -> str:
    safe_name = _safe_filename(repository_name).removesuffix(".zip")
    return f"{safe_name or 'repository'}-export.zip"


def _read_payloads(
    archive: ZipFile,
    manifest: ExportBundleManifest,
    names: set[str],
    errors: list[ExportBundleValidationIssue],
) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    for payload_name, path in manifest.payloads.items():
        if path not in names:
            errors.append(
                _issue(
                    "error",
                    "missing_payload",
                    f"Bundle is missing payload '{payload_name}' at {path}.",
                    path=path,
                )
            )
            continue
        try:
            payloads[payload_name] = json.loads(archive.read(path))
        except json.JSONDecodeError as exc:
            errors.append(
                _issue(
                    "error",
                    "invalid_payload_json",
                    f"Payload '{payload_name}' is not valid JSON: {exc.msg}.",
                    path=path,
                )
            )
    return payloads


def _validate_source_entries(
    archive: ZipFile,
    names: set[str],
    manifest: ExportBundleManifest,
    source_mappings: Sequence[ExportBundleSourceMapping],
    errors: list[ExportBundleValidationIssue],
    warnings: list[ExportBundleValidationIssue],
    informational: list[ExportBundleValidationIssue],
) -> None:
    mappings_by_version = {
        mapping.document_version_id: mapping
        for mapping in source_mappings
        if mapping.document_version_id is not None
    }
    mappings_by_hash = {mapping.sha256: mapping for mapping in source_mappings}
    for source in manifest.sources:
        if source.included:
            _validate_included_source(archive, names, source, errors, informational)
        else:
            _validate_external_source_mapping(
                source=source,
                mapping=mappings_by_version.get(source.document_version_id)
                or mappings_by_hash.get(source.sha256),
                errors=errors,
                warnings=warnings,
                informational=informational,
            )


def _validate_included_source(
    archive: ZipFile,
    names: set[str],
    source: ExportBundleSource,
    errors: list[ExportBundleValidationIssue],
    informational: list[ExportBundleValidationIssue],
) -> None:
    if source.bundle_path is None or source.bundle_path not in names:
        errors.append(
            _issue(
                "error",
                "missing_bundle_source",
                f"Included source file is missing from the bundle: {source.original_filename}.",
                path=source.bundle_path,
                source_sha256=source.sha256,
                document_version_id=source.document_version_id,
            )
        )
        return

    data = archive.read(source.bundle_path)
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != source.sha256:
        errors.append(
            _issue(
                "error",
                "source_hash_mismatch",
                f"Included source hash does not match manifest for {source.original_filename}.",
                path=source.bundle_path,
                source_sha256=source.sha256,
                document_version_id=source.document_version_id,
            )
        )
        return
    if len(data) != source.byte_size:
        errors.append(
            _issue(
                "error",
                "source_size_mismatch",
                f"Included source byte size does not match manifest for {source.original_filename}.",
                path=source.bundle_path,
                source_sha256=source.sha256,
                document_version_id=source.document_version_id,
            )
        )
        return
    informational.append(
        _issue(
            "info",
            "source_hash_verified",
            f"Included source hash verified for {source.original_filename}.",
            path=source.bundle_path,
            source_sha256=source.sha256,
            document_version_id=source.document_version_id,
        )
    )


def _validate_external_source_mapping(
    source: ExportBundleSource,
    mapping: ExportBundleSourceMapping | None,
    errors: list[ExportBundleValidationIssue],
    warnings: list[ExportBundleValidationIssue],
    informational: list[ExportBundleValidationIssue],
) -> None:
    if mapping is None:
        errors.append(
            _issue(
                "error",
                "missing_external_source_mapping",
                f"Source file is not included and needs an external mapping: {source.original_filename}.",
                source_sha256=source.sha256,
                document_version_id=source.document_version_id,
            )
        )
        return

    mapped_path = Path(mapping.path).expanduser()
    if not mapped_path.exists():
        errors.append(
            _issue(
                "error",
                "external_source_missing",
                f"Mapped source file does not exist: {mapping.path}.",
                path=mapping.path,
                source_sha256=source.sha256,
                document_version_id=source.document_version_id,
            )
        )
        return

    actual_sha256 = sha256_file(mapped_path)
    if actual_sha256 != source.sha256:
        errors.append(
            _issue(
                "error",
                "external_source_hash_mismatch",
                f"Mapped source hash does not match manifest for {source.original_filename}.",
                path=mapping.path,
                source_sha256=source.sha256,
                document_version_id=source.document_version_id,
            )
        )
        return

    if mapped_path.name != source.original_filename:
        warnings.append(
            _issue(
                "warning",
                "external_source_renamed",
                f"Mapped source filename differs from export metadata: {source.original_filename}.",
                path=mapping.path,
                source_sha256=source.sha256,
                document_version_id=source.document_version_id,
            )
        )
    informational.append(
        _issue(
            "info",
            "external_source_hash_verified",
            f"External source hash verified for {source.original_filename}.",
            path=mapping.path,
            source_sha256=source.sha256,
            document_version_id=source.document_version_id,
        )
    )


def _validate_models(
    manifest: ExportBundleManifest,
    available_models: Sequence[str] | None,
    warnings: list[ExportBundleValidationIssue],
    informational: list[ExportBundleValidationIssue],
) -> None:
    if available_models is None:
        for model in manifest.required_models:
            warnings.append(
                _issue(
                    "warning",
                    "model_availability_unconfirmed",
                    f"Required model availability was not checked: {model}.",
                    setting="model",
                )
            )
        return

    available = set(available_models)
    for model in manifest.required_models:
        if model not in available:
            warnings.append(
                _issue(
                    "warning",
                    "missing_model",
                    f"Required model is not available: {model}.",
                    setting="model",
                )
            )
        else:
            informational.append(
                _issue(
                    "info",
                    "model_available",
                    f"Required model is available: {model}.",
                    setting="model",
                )
            )


def _validate_counts(
    manifest: ExportBundleManifest,
    payloads: Mapping[str, Any],
    errors: list[ExportBundleValidationIssue],
) -> None:
    actual_counts = {
        "sources": len(manifest.sources),
        "included_sources": sum(1 for source in manifest.sources if source.included),
        "documents": len(_payload_list(payloads, "documents", "documents")),
        "document_versions": len(_payload_list(payloads, "documents", "versions")),
        "chunks": len(_payload_list(payloads, "chunks", "chunks")),
        "chat_sessions": len(_payload_list(payloads, "chat", "sessions")),
        "chat_messages": len(_payload_list(payloads, "chat", "messages")),
        "chat_citations": sum(
            len(message.get("citations") or {})
            for message in _payload_list(payloads, "chat", "messages")
            if isinstance(message, dict)
        ),
        "retrieval_runs": len(_payload_list(payloads, "retrieval", "runs")),
        "retrieval_results": len(_payload_list(payloads, "retrieval", "results")),
        "sandbox_prompt_versions": len(_payload_list(payloads, "sandbox", "prompt_versions")),
        "sandbox_runs": len(_payload_list(payloads, "sandbox", "runs")),
        "sandbox_comparisons": len(_payload_list(payloads, "sandbox", "comparisons")),
    }
    for name, expected in manifest.counts.items():
        actual = actual_counts.get(name)
        if actual is not None and actual != expected:
            errors.append(
                _issue(
                    "error",
                    "count_mismatch",
                    f"Manifest count for {name} is {expected}, but payload contains {actual}.",
                )
            )


def _report_parser_fingerprints(
    payloads: Mapping[str, Any],
    informational: list[ExportBundleValidationIssue],
) -> None:
    versions = _payload_list(payloads, "documents", "versions")
    seen: set[tuple[str, str, int]] = set()
    for version in versions:
        if not isinstance(version, dict):
            continue
        parser_name = str(version.get("parser_name") or "unknown")
        parser_version = str(version.get("parser_version") or "unknown")
        chunk_count = int(version.get("chunk_count") or 0)
        fingerprint = (parser_name, parser_version, chunk_count)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        informational.append(
            _issue(
                "info",
                "parser_fingerprint",
                f"Exported parser fingerprint: {parser_name} {parser_version}, {chunk_count} chunks.",
            )
        )


def _payload_list(payloads: Mapping[str, Any], payload_name: str, field: str) -> list[Any]:
    payload = payloads.get(payload_name)
    if not isinstance(payload, dict):
        return []
    value = payload.get(field)
    return value if isinstance(value, list) else []


def _unsupported_schema_issue(payload: Any) -> ExportBundleValidationIssue | None:
    if not isinstance(payload, dict):
        return _issue(
            "error",
            "invalid_manifest_schema",
            "manifest.json must contain a JSON object.",
            path=MANIFEST_PATH,
        )
    schema_version = payload.get("bundle_schema_version")
    if schema_version != 1:
        return _issue(
            "error",
            "unsupported_schema_version",
            f"Unsupported export bundle schema version: {schema_version}.",
            path=MANIFEST_PATH,
        )
    return None


def _validation_response(
    errors: list[ExportBundleValidationIssue] | None = None,
) -> ExportBundleValidationResponse:
    blocking_errors = errors or []
    return ExportBundleValidationResponse(
        can_recreate=not blocking_errors,
        blocking_errors=blocking_errors,
    )


def _issue(
    severity: Literal["error", "warning", "info"],
    code: str,
    message: str,
    path: str | None = None,
    setting: str | None = None,
    source_sha256: str | None = None,
    document_version_id: str | None = None,
) -> ExportBundleValidationIssue:
    return ExportBundleValidationIssue(
        severity=severity,
        code=code,
        message=message,
        path=path,
        setting=setting,
        source_sha256=source_sha256,
        document_version_id=document_version_id,
    )
