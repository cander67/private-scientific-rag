from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from private_rag.core.settings import Settings, get_settings
from private_rag.ingestion.models import Document, DocumentChunk, DocumentVersion
from private_rag.ingestion.parser import ParserExecutionSettings, detect_source_type, parse_source
from private_rag.ingestion.schemas import (
    DocumentChunkRead,
    DocumentInspection,
    DocumentRead,
    DocumentStatus,
    DocumentUploadResponse,
    DocumentVersionRead,
    PageImageRead,
    ParsedDocument,
    ParsedSegment,
    SourceType,
)
from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import RepositorySettings


class ParserChunkStaleError(RuntimeError):
    def __init__(self, stale_documents: list[dict[str, object]]) -> None:
        self.stale_documents = stale_documents
        super().__init__(_stale_documents_message(stale_documents))


def upload_document(
    session: Session,
    repository_id: str,
    filename: str,
    content_type: str | None,
    data: bytes,
    settings: Settings | None = None,
) -> DocumentUploadResponse | None:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    repository_settings = RepositorySettings.model_validate(repository.settings.settings)

    digest = hashlib.sha256(data).hexdigest()
    existing_version = session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.repository_id == repository_id,
            DocumentVersion.sha256 == digest,
            DocumentVersion.original_filename == filename,
        )
    )
    if existing_version is not None:
        return _upload_response(
            existing_version, skipped=True, repository_settings=repository_settings
        )

    app_settings = settings or get_settings()
    storage_path = _write_source_file(repository_id, filename, digest, data, app_settings)
    parsed = _parse_document_safely(filename, content_type, data, repository_settings)
    _attach_annotation_pair_metadata(session, repository_id, filename, parsed)
    _attach_parser_fingerprint(
        parsed=parsed,
        repository_settings=repository_settings,
        source_hash=digest,
    )

    document = Document(repository_id=repository_id, display_name=filename)
    session.add(document)
    session.flush()

    version = DocumentVersion(
        document_id=document.id,
        repository_id=repository_id,
        original_filename=filename,
        content_type=content_type,
        source_type=parsed.source_type,
        sha256=digest,
        byte_size=len(data),
        storage_path=str(storage_path),
        status=_status_for_parsed_document(parsed),
        parser_name=parsed.parser_name,
        parser_version=parsed.parser_version,
        ocr_required=parsed.ocr_required,
        page_count=parsed.page_count,
        line_count=parsed.line_count,
        section_count=len(parsed.sections),
        chunk_count=0,
        warnings=parsed.warnings,
        extra_metadata=parsed.metadata,
    )
    session.add(version)
    session.flush()

    _attach_page_image_metadata(
        data=data,
        parsed=parsed,
        version=version,
        document_id=document.id,
        settings=app_settings,
    )

    chunks = _chunk_parsed_document(
        parsed=parsed,
        repository_id=repository_id,
        document_id=document.id,
        document_version_id=version.id,
        chunk_size=repository_settings.chunking.chunk_size,
        chunk_overlap=repository_settings.chunking.chunk_overlap,
        source_hash=digest,
        parser_version=parsed.parser_version,
    )
    session.add_all(chunks)
    version.chunk_count = len(chunks)
    document.current_version_id = version.id
    session.add(document)
    session.commit()
    session.refresh(version)
    session.refresh(document)
    return _upload_response(version, repository_settings=repository_settings)


def list_documents(session: Session, repository_id: str) -> list[DocumentRead] | None:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    repository_settings = RepositorySettings.model_validate(repository.settings.settings)
    documents = session.scalars(
        select(Document)
        .where(Document.repository_id == repository_id)
        .order_by(Document.created_at)
    ).all()
    return [
        _document_read(
            document, _current_version(document), repository_settings=repository_settings
        )
        for document in documents
    ]


def inspect_document(
    session: Session,
    repository_id: str,
    document_id: str,
) -> DocumentInspection | None:
    document = session.get(Document, document_id)
    if document is None or document.repository_id != repository_id:
        return None
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    repository_settings = RepositorySettings.model_validate(repository.settings.settings)
    version = _current_version(document)
    if version is None:
        return None
    return _inspection_for_version(
        session=session,
        document=document,
        version=version,
        repository_settings=repository_settings,
    )


def inspect_document_version(
    session: Session,
    repository_id: str,
    document_id: str,
    version_id: str,
) -> DocumentInspection | None:
    document = session.get(Document, document_id)
    if document is None or document.repository_id != repository_id:
        return None
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    version = next((item for item in document.versions if item.id == version_id), None)
    if version is None:
        return None
    return _inspection_for_version(
        session=session,
        document=document,
        version=version,
        repository_settings=RepositorySettings.model_validate(repository.settings.settings),
    )


def stale_parser_chunk_documents(
    session: Session,
    repository_id: str,
    repository_settings: RepositorySettings,
) -> list[dict[str, object]]:
    rows = session.execute(
        select(Document, DocumentVersion)
        .join(DocumentVersion, DocumentVersion.id == Document.current_version_id)
        .where(Document.repository_id == repository_id)
        .order_by(Document.display_name)
    ).all()
    stale_documents: list[dict[str, object]] = []
    for document, version in rows:
        status = _reprocess_status_metadata(version, repository_settings)
        if status["status"] != "stale":
            continue
        stale_documents.append(
            {
                "document_id": document.id,
                "document_version_id": version.id,
                "document_title": document.display_name,
                "changed_fields": status["changed_fields"],
                "message": status["message"],
            }
        )
    return stale_documents


def _inspection_for_version(
    session: Session,
    document: Document,
    version: DocumentVersion,
    repository_settings: RepositorySettings,
) -> DocumentInspection:
    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_version_id == version.id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    return DocumentInspection(
        document=_document_read(
            document, _current_version(document), repository_settings=repository_settings
        ),
        version=_version_read(version, repository_settings=repository_settings),
        chunks=[_chunk_read(chunk) for chunk in chunks],
        page_images=_page_images_from_metadata(version.extra_metadata),
    )


def reprocess_document(
    session: Session,
    repository_id: str,
    document_id: str,
) -> DocumentInspection | None:
    document = session.get(Document, document_id)
    if document is None or document.repository_id != repository_id:
        return None
    version = _current_version(document)
    if version is None:
        return None
    source_path = Path(version.storage_path)
    if not source_path.exists():
        missing_version = _new_reprocess_version(
            source_version=version,
            status="failed",
            parser_name=version.parser_name,
            parser_version=version.parser_version,
            byte_size=version.byte_size,
            sha256=version.sha256,
            warnings=[*version.warnings, "Original source file is missing."],
            metadata={
                **version.extra_metadata,
                "reprocess": {
                    "source_version_id": version.id,
                    "status": "failed",
                    "message": "Original source file is missing.",
                },
            },
        )
        session.add(missing_version)
        session.flush()
        document.current_version_id = missing_version.id
        session.add(document)
        session.commit()
        return inspect_document(session, repository_id, document_id)

    data = source_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    repository_settings = RepositorySettings.model_validate(repository.settings.settings)
    parsed = _parse_document_safely(
        version.original_filename,
        version.content_type,
        data,
        repository_settings,
    )
    _attach_annotation_pair_metadata(session, repository_id, version.original_filename, parsed)
    _attach_parser_fingerprint(
        parsed=parsed,
        repository_settings=repository_settings,
        source_hash=digest,
    )
    previous_fingerprint = str(version.extra_metadata.get("parser_fingerprint") or "")
    next_fingerprint = str(parsed.metadata.get("parser_fingerprint") or "")
    parsed.metadata["reprocess"] = {
        "source_version_id": version.id,
        "previous_parser_fingerprint": previous_fingerprint,
        "new_parser_fingerprint": next_fingerprint,
        "fingerprint_changed": previous_fingerprint != next_fingerprint,
        "changed_fields": _parser_fingerprint_changed_fields(
            _dict_or_empty(version.extra_metadata.get("parser_fingerprint_payload")),
            _dict_or_empty(parsed.metadata.get("parser_fingerprint_payload")),
        ),
    }

    new_version = _new_reprocess_version(
        source_version=version,
        status=_status_for_parsed_document(parsed),
        parser_name=parsed.parser_name,
        parser_version=parsed.parser_version,
        byte_size=len(data),
        sha256=digest,
        source_type=parsed.source_type,
        ocr_required=parsed.ocr_required,
        page_count=parsed.page_count,
        line_count=parsed.line_count,
        section_count=len(parsed.sections),
        warnings=parsed.warnings,
        metadata=parsed.metadata,
    )
    session.add(new_version)
    session.flush()
    chunks = _chunk_parsed_document(
        parsed=parsed,
        repository_id=repository_id,
        document_id=document.id,
        document_version_id=new_version.id,
        chunk_size=repository_settings.chunking.chunk_size,
        chunk_overlap=repository_settings.chunking.chunk_overlap,
        source_hash=digest,
        parser_version=parsed.parser_version,
    )
    session.add_all(chunks)
    new_version.chunk_count = len(chunks)
    document.current_version_id = new_version.id
    session.add(document)
    _attach_page_image_metadata(
        data=data,
        parsed=parsed,
        version=new_version,
        document_id=document.id,
        settings=get_settings(),
    )
    session.add(new_version)
    session.commit()
    return inspect_document(session, repository_id, document_id)


def delete_document(session: Session, repository_id: str, document_id: str) -> bool | None:
    document = session.get(Document, document_id)
    if document is None:
        return None
    if document.repository_id != repository_id:
        return None
    for version in document.versions:
        _delete_version_artifacts(version)
    session.delete(document)
    session.commit()
    return True


def delete_all_documents(session: Session, repository_id: str) -> int | None:
    if session.get(Repository, repository_id) is None:
        return None
    documents = session.scalars(
        select(Document).where(Document.repository_id == repository_id)
    ).all()
    for document in documents:
        for version in document.versions:
            _delete_version_artifacts(version)
        session.delete(document)
    session.commit()
    return len(documents)


def document_page_image_path(
    session: Session,
    repository_id: str,
    document_id: str,
    version_id: str,
    page: int,
) -> Path | None:
    document = session.get(Document, document_id)
    if document is None or document.repository_id != repository_id:
        return None
    version = next((item for item in document.versions if item.id == version_id), None)
    if version is None:
        return None
    for image in _page_images_from_metadata(version.extra_metadata):
        if image.page == page:
            path = _page_image_disk_path(version, page)
            if path.exists():
                return path
    return None


def _parse_document_safely(
    filename: str,
    content_type: str | None,
    data: bytes,
    repository_settings: RepositorySettings | None = None,
) -> ParsedDocument:
    try:
        parser_settings = None
        if repository_settings is not None:
            parser_settings = ParserExecutionSettings(
                structured_parser=repository_settings.parser.structured_parser,
                fallback_parser=repository_settings.parser.fallback_parser,
            )
        return parse_source(filename, content_type, data, parser_settings=parser_settings)
    except Exception as exc:
        return ParsedDocument(
            source_type=detect_source_type(filename, content_type),
            text="",
            parser_name="private-rag-built-in",
            parser_version="prd3-v1",
            warnings=[f"Parsing failed: {type(exc).__name__}: {exc}"],
            metadata={"parse_error": type(exc).__name__},
        )


def _new_reprocess_version(
    source_version: DocumentVersion,
    status: DocumentStatus,
    parser_name: str,
    parser_version: str,
    byte_size: int,
    sha256: str,
    source_type: SourceType | None = None,
    ocr_required: bool | None = None,
    page_count: int | None = None,
    line_count: int | None = None,
    section_count: int | None = None,
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DocumentVersion:
    return DocumentVersion(
        document_id=source_version.document_id,
        repository_id=source_version.repository_id,
        original_filename=source_version.original_filename,
        content_type=source_version.content_type,
        source_type=source_type or cast(SourceType, source_version.source_type),
        sha256=sha256,
        byte_size=byte_size,
        storage_path=source_version.storage_path,
        status=status,
        parser_name=parser_name,
        parser_version=parser_version,
        ocr_required=source_version.ocr_required if ocr_required is None else ocr_required,
        page_count=source_version.page_count if page_count is None else page_count,
        line_count=source_version.line_count if line_count is None else line_count,
        section_count=source_version.section_count if section_count is None else section_count,
        chunk_count=0,
        warnings=warnings or [],
        extra_metadata=metadata or {},
    )


def _attach_parser_fingerprint(
    parsed: ParsedDocument,
    repository_settings: RepositorySettings,
    source_hash: str,
) -> None:
    payload = _parser_fingerprint_payload(
        parsed=parsed,
        repository_settings=repository_settings,
        source_hash=source_hash,
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    parsed.metadata["parser_fingerprint"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    parsed.metadata["parser_fingerprint_payload"] = payload


def _parser_fingerprint_payload(
    parsed: ParsedDocument,
    repository_settings: RepositorySettings,
    source_hash: str,
) -> dict[str, object]:
    return {
        "parser": repository_settings.parser.model_dump(mode="json"),
        "parser_package_versions": parsed.metadata.get("parser_package_versions", {}),
        "parser_quality_thresholds": parsed.metadata.get("parser_quality_thresholds", {}),
        "source_hash": source_hash,
        "chunking": repository_settings.chunking.model_dump(mode="json"),
    }


def _parser_fingerprint_changed_fields(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    changed_fields: list[str] = []
    for field in (
        "parser.structured_parser",
        "parser.fallback_parser",
        "chunking.mode",
        "chunking.chunk_size",
        "chunking.chunk_overlap",
        "source_hash",
    ):
        if _nested_value(previous, field) != _nested_value(current, field):
            changed_fields.append(field)
    return changed_fields


def _nested_value(payload: dict[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for key in dotted_path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _dict_or_empty(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _version_metadata(
    version: DocumentVersion,
    repository_settings: RepositorySettings | None,
) -> dict[str, Any]:
    metadata = dict(version.extra_metadata or {})
    if repository_settings is not None:
        metadata["reprocess_status"] = _reprocess_status_metadata(version, repository_settings)
    return metadata


def _reprocess_status_metadata(
    version: DocumentVersion,
    repository_settings: RepositorySettings,
) -> dict[str, Any]:
    payload = _dict_or_empty(version.extra_metadata.get("parser_fingerprint_payload"))
    stored_fingerprint = str(version.extra_metadata.get("parser_fingerprint") or "")
    if not payload or not stored_fingerprint:
        return {
            "status": "unknown",
            "stale": False,
            "reprocess_available": Path(version.storage_path).exists(),
            "message": "Parser fingerprint metadata is not available for this version.",
            "changed_fields": [],
        }

    current_payload = {
        **payload,
        "parser": repository_settings.parser.model_dump(mode="json"),
        "chunking": repository_settings.chunking.model_dump(mode="json"),
    }
    encoded = json.dumps(current_payload, sort_keys=True, separators=(",", ":"))
    current_fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    changed_fields = _parser_fingerprint_changed_fields(payload, current_payload)
    source_exists = Path(version.storage_path).exists()
    if not source_exists:
        status = "source_missing"
        message = "Stored source file is missing; reprocess cannot run until it is restored."
    elif current_fingerprint != stored_fingerprint:
        status = "stale"
        message = "Parser or chunking settings changed since this version was parsed."
    else:
        status = "current"
        message = "Parser and chunking settings match this parsed version."
    return {
        "status": status,
        "stale": status == "stale",
        "reprocess_available": source_exists,
        "stored_parser_fingerprint": stored_fingerprint,
        "current_parser_fingerprint": current_fingerprint,
        "changed_fields": changed_fields,
        "message": message,
    }


def _stale_documents_message(stale_documents: list[dict[str, object]]) -> str:
    if not stale_documents:
        return "Parser or chunking settings changed; reprocess stale documents before rebuilding indexes."
    previews = []
    for document in stale_documents[:5]:
        title = str(document.get("document_title") or document.get("document_id") or "document")
        fields = document.get("changed_fields")
        field_text = ", ".join(str(field) for field in fields) if isinstance(fields, list) else ""
        previews.append(f"{title}{f' ({field_text})' if field_text else ''}")
    suffix = ""
    if len(stale_documents) > len(previews):
        suffix = f" and {len(stale_documents) - len(previews)} more"
    return (
        "Parser/chunk settings are stale for "
        f"{len(stale_documents)} document(s): {', '.join(previews)}{suffix}. "
        "Reprocess stale documents before rebuilding indexes."
    )


def _status_for_parsed_document(parsed: ParsedDocument) -> DocumentStatus:
    if parsed.metadata.get("parse_error"):
        return "failed"
    if parsed.ocr_required:
        return "needs_ocr"
    return "parsed"


def _write_source_file(
    repository_id: str,
    filename: str,
    digest: str,
    data: bytes,
    settings: Settings | None,
) -> Path:
    app_settings = settings or get_settings()
    destination_dir = app_settings.data_dir / "repositories" / repository_id / "sources"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{digest[:12]}-{_safe_filename(filename)}"
    destination.write_bytes(data)
    return destination


def _attach_annotation_pair_metadata(
    session: Session,
    repository_id: str,
    filename: str,
    parsed: ParsedDocument,
) -> None:
    if parsed.source_type != "annotation":
        return
    paired_version = _find_paired_text_version(session, repository_id, filename)
    if paired_version is None:
        parsed.metadata["paired_text_missing"] = True
        return
    parsed.metadata.update(
        {
            "paired_text_document_id": paired_version.document_id,
            "paired_text_version_id": paired_version.id,
            "paired_text_filename": paired_version.original_filename,
        }
    )


def _find_paired_text_version(
    session: Session,
    repository_id: str,
    filename: str,
) -> DocumentVersion | None:
    basename = Path(filename).stem
    candidates = {f"{basename}.txt", f"{basename}.text"}
    return session.scalar(
        select(DocumentVersion)
        .where(
            DocumentVersion.repository_id == repository_id,
            DocumentVersion.source_type == "text",
            DocumentVersion.original_filename.in_(candidates),
        )
        .order_by(DocumentVersion.created_at.desc())
    )


def _attach_page_image_metadata(
    data: bytes,
    parsed: ParsedDocument,
    version: DocumentVersion,
    document_id: str,
    settings: Settings,
) -> None:
    if parsed.source_type != "pdf":
        return
    page_images, warnings = _render_pdf_page_images(
        data=data,
        repository_id=version.repository_id,
        document_id=document_id,
        version_id=version.id,
        page_count=parsed.page_count,
        settings=settings,
    )
    metadata = {**version.extra_metadata, "page_images": page_images}
    metadata["page_images_available"] = bool(page_images)
    version.extra_metadata = metadata
    if warnings:
        version.warnings = [*version.warnings, *warnings]


def _render_pdf_page_images(
    data: bytes,
    repository_id: str,
    document_id: str,
    version_id: str,
    page_count: int | None,
    settings: Settings,
) -> tuple[list[dict[str, object]], list[str]]:
    try:
        import fitz
    except Exception as exc:
        return [], [f"Page thumbnails unavailable: PyMuPDF import failed ({type(exc).__name__})."]

    destination_dir = (
        settings.data_dir / "repositories" / repository_id / "derived" / version_id / "page-images"
    )
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    try:
        document = fitz.open(stream=data, filetype="pdf")
        render_count = page_count or document.page_count
        page_images: list[dict[str, object]] = []
        for page_index in range(min(render_count, document.page_count)):
            page_number = page_index + 1
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(0.35, 0.35), alpha=False)
            destination = destination_dir / _page_image_filename(page_number)
            pixmap.save(destination)
            image_bytes = destination.read_bytes()
            page_images.append(
                {
                    "page": page_number,
                    "url": (
                        f"/repositories/{repository_id}/documents/{document_id}/versions/"
                        f"{version_id}/page-images/{page_number}"
                    ),
                    "mime_type": "image/png",
                    "width": pixmap.width,
                    "height": pixmap.height,
                    "byte_size": len(image_bytes),
                    "sha256": hashlib.sha256(image_bytes).hexdigest(),
                }
            )
        return page_images, []
    except Exception as exc:
        shutil.rmtree(destination_dir, ignore_errors=True)
        return [], [f"Page thumbnails unavailable: PDF render failed ({type(exc).__name__})."]


def _page_image_filename(page: int) -> str:
    return f"page-{page:04d}.png"


def _page_image_disk_path(version: DocumentVersion, page: int) -> Path:
    return (
        Path(version.storage_path).parents[1]
        / "derived"
        / version.id
        / "page-images"
        / _page_image_filename(page)
    )


def _delete_version_artifacts(version: DocumentVersion) -> None:
    derived_dir = Path(version.storage_path).parents[1] / "derived" / version.id
    shutil.rmtree(derived_dir, ignore_errors=True)


def _page_images_from_metadata(metadata: dict[str, object]) -> list[PageImageRead]:
    page_images = metadata.get("page_images")
    if not isinstance(page_images, list):
        return []
    parsed_images: list[PageImageRead] = []
    for image in page_images:
        if isinstance(image, dict):
            parsed_images.append(PageImageRead.model_validate(image))
    return parsed_images


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).name).strip("-")
    return cleaned or "document"


def _chunk_parsed_document(
    parsed: ParsedDocument,
    repository_id: str,
    document_id: str,
    document_version_id: str,
    chunk_size: int,
    chunk_overlap: int,
    source_hash: str,
    parser_version: str,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for segment in _coalesce_segments(parsed.segments, chunk_size, chunk_overlap):
        text = segment.text.strip()
        if not text:
            continue
        chunks.append(
            DocumentChunk(
                repository_id=repository_id,
                document_id=document_id,
                document_version_id=document_version_id,
                chunk_index=len(chunks),
                text=text,
                section=segment.section,
                page_start=segment.page_start,
                page_end=segment.page_end,
                line_start=segment.line_start,
                line_end=segment.line_end,
                char_start=segment.char_start,
                char_end=segment.char_end,
                parser_version=parser_version,
                extra_metadata={
                    **segment.metadata,
                    "source_hash": source_hash,
                    "source_type": parsed.source_type,
                    "parser_name": parsed.parser_name,
                    "parser_route": parsed.metadata.get("parser_route")
                    or parsed.metadata.get("parser_chain", []),
                    "parser_settings": parsed.metadata.get("parser_settings", {}),
                    "parser_fingerprint": parsed.metadata.get("parser_fingerprint", ""),
                },
            )
        )
    return chunks


def _coalesce_segments(
    segments: list[ParsedSegment],
    chunk_size: int,
    chunk_overlap: int,
) -> list[ParsedSegment]:
    if not segments:
        return []

    chunks: list[ParsedSegment] = []
    current: list[ParsedSegment] = []
    current_length = 0
    for segment in segments:
        segment_length = len(segment.text)
        if current and current_length + segment_length + 1 > chunk_size:
            chunks.append(_merge_segments(current))
            current = _overlap_tail(current, chunk_overlap)
            current_length = sum(len(item.text) + 1 for item in current)
        current.append(segment)
        current_length += segment_length + 1

    if current:
        chunks.append(_merge_segments(current))
    return chunks


def _overlap_tail(segments: list[ParsedSegment], chunk_overlap: int) -> list[ParsedSegment]:
    if chunk_overlap <= 0:
        return []
    tail: list[ParsedSegment] = []
    length = 0
    for segment in reversed(segments):
        if tail and length + len(segment.text) > chunk_overlap:
            break
        tail.insert(0, segment)
        length += len(segment.text) + 1
    return tail


def _merge_segments(segments: list[ParsedSegment]) -> ParsedSegment:
    first = segments[0]
    last = segments[-1]
    return ParsedSegment(
        text="\n".join(segment.text for segment in segments),
        section=last.section or first.section,
        page_start=_first_value(segment.page_start for segment in segments),
        page_end=_last_value(segment.page_end for segment in segments),
        line_start=_first_value(segment.line_start for segment in segments),
        line_end=_last_value(segment.line_end for segment in segments),
        char_start=first.char_start,
        char_end=last.char_end,
        metadata={
            "segment_count": len(segments),
            "sections": [
                section
                for section in dict.fromkeys(segment.section for segment in segments)
                if section
            ],
        },
    )


def _first_value(values: Iterable[int | None]) -> int | None:
    return next((value for value in values if value is not None), None)


def _last_value(values: Iterable[int | None]) -> int | None:
    return next((value for value in reversed(list(values)) if value is not None), None)


def _upload_response(
    version: DocumentVersion,
    skipped: bool = False,
    repository_settings: RepositorySettings | None = None,
) -> DocumentUploadResponse:
    if skipped:
        version.status = "skipped"
    document = version.document
    chunks_preview = version.chunks[:5]
    return DocumentUploadResponse(
        document=_document_read(document, version, repository_settings=repository_settings),
        version=_version_read(version, repository_settings=repository_settings),
        chunks_preview=[_chunk_read(chunk) for chunk in chunks_preview],
    )


def _current_version(document: Document) -> DocumentVersion | None:
    if document.current_version_id is None:
        return document.versions[-1] if document.versions else None
    return next(
        (version for version in document.versions if version.id == document.current_version_id),
        document.versions[-1] if document.versions else None,
    )


def _document_read(
    document: Document,
    version: DocumentVersion | None = None,
    repository_settings: RepositorySettings | None = None,
) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        repository_id=document.repository_id,
        display_name=document.display_name,
        current_version_id=document.current_version_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
        current_version=(
            _version_read(version, repository_settings=repository_settings)
            if version is not None
            else None
        ),
    )


def _version_read(
    version: DocumentVersion,
    repository_settings: RepositorySettings | None = None,
) -> DocumentVersionRead:
    return DocumentVersionRead(
        id=version.id,
        document_id=version.document_id,
        repository_id=version.repository_id,
        original_filename=version.original_filename,
        content_type=version.content_type,
        source_type=cast(SourceType, version.source_type),
        sha256=version.sha256,
        byte_size=version.byte_size,
        storage_path=version.storage_path,
        status=cast(DocumentStatus, version.status),
        parser_name=version.parser_name,
        parser_version=version.parser_version,
        ocr_required=version.ocr_required,
        page_count=version.page_count,
        line_count=version.line_count,
        section_count=version.section_count,
        chunk_count=version.chunk_count,
        warnings=version.warnings,
        metadata=_version_metadata(version, repository_settings),
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def _chunk_read(chunk: DocumentChunk) -> DocumentChunkRead:
    return DocumentChunkRead(
        id=chunk.id,
        repository_id=chunk.repository_id,
        document_id=chunk.document_id,
        document_version_id=chunk.document_version_id,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        section=chunk.section,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        parser_version=chunk.parser_version,
        source_hash=str(chunk.extra_metadata.get("source_hash", "")),
        metadata=chunk.extra_metadata,
    )
