from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from private_rag.core.settings import Settings, get_settings
from private_rag.ingestion.models import Document, DocumentChunk, DocumentVersion
from private_rag.ingestion.parser import detect_source_type, parse_source
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

    digest = hashlib.sha256(data).hexdigest()
    existing_version = session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.repository_id == repository_id,
            DocumentVersion.sha256 == digest,
            DocumentVersion.original_filename == filename,
        )
    )
    if existing_version is not None:
        return _upload_response(existing_version, skipped=True)

    app_settings = settings or get_settings()
    storage_path = _write_source_file(repository_id, filename, digest, data, app_settings)
    parsed = _parse_document_safely(filename, content_type, data)
    _attach_annotation_pair_metadata(session, repository_id, filename, parsed)
    repository_settings = RepositorySettings.model_validate(repository.settings.settings)

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
    return _upload_response(version)


def list_documents(session: Session, repository_id: str) -> list[DocumentRead] | None:
    if session.get(Repository, repository_id) is None:
        return None
    documents = session.scalars(
        select(Document)
        .where(Document.repository_id == repository_id)
        .order_by(Document.created_at)
    ).all()
    return [_document_read(document, _current_version(document)) for document in documents]


def inspect_document(
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
    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_version_id == version.id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    return DocumentInspection(
        document=_document_read(document, version),
        version=_version_read(version),
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
        version.status = "failed"
        version.warnings = [*version.warnings, "Original source file is missing."]
        session.add(version)
        session.commit()
        return inspect_document(session, repository_id, document_id)

    data = source_path.read_bytes()
    parsed = _parse_document_safely(version.original_filename, version.content_type, data)
    _attach_annotation_pair_metadata(session, repository_id, version.original_filename, parsed)
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    repository_settings = RepositorySettings.model_validate(repository.settings.settings)

    session.query(DocumentChunk).filter(DocumentChunk.document_version_id == version.id).delete(
        synchronize_session=False
    )
    chunks = _chunk_parsed_document(
        parsed=parsed,
        repository_id=repository_id,
        document_id=document.id,
        document_version_id=version.id,
        chunk_size=repository_settings.chunking.chunk_size,
        chunk_overlap=repository_settings.chunking.chunk_overlap,
        source_hash=version.sha256,
        parser_version=parsed.parser_version,
    )
    session.add_all(chunks)
    version.status = _status_for_parsed_document(parsed)
    version.parser_name = parsed.parser_name
    version.parser_version = parsed.parser_version
    version.ocr_required = parsed.ocr_required
    version.page_count = parsed.page_count
    version.line_count = parsed.line_count
    version.section_count = len(parsed.sections)
    version.chunk_count = len(chunks)
    version.warnings = parsed.warnings
    version.extra_metadata = parsed.metadata
    _attach_page_image_metadata(
        data=data,
        parsed=parsed,
        version=version,
        document_id=document.id,
        settings=get_settings(),
    )
    session.add(version)
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
    documents = session.scalars(select(Document).where(Document.repository_id == repository_id)).all()
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
) -> ParsedDocument:
    try:
        return parse_source(filename, content_type, data)
    except Exception as exc:
        return ParsedDocument(
            source_type=detect_source_type(filename, content_type),
            text="",
            parser_name="private-rag-built-in",
            parser_version="prd3-v1",
            warnings=[f"Parsing failed: {type(exc).__name__}: {exc}"],
            metadata={"parse_error": type(exc).__name__},
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
) -> DocumentUploadResponse:
    if skipped:
        version.status = "skipped"
    document = version.document
    chunks_preview = version.chunks[:5]
    return DocumentUploadResponse(
        document=_document_read(document, version),
        version=_version_read(version),
        chunks_preview=[_chunk_read(chunk) for chunk in chunks_preview],
    )


def _current_version(document: Document) -> DocumentVersion | None:
    if document.current_version_id is None:
        return document.versions[-1] if document.versions else None
    return next(
        (version for version in document.versions if version.id == document.current_version_id),
        document.versions[-1] if document.versions else None,
    )


def _document_read(document: Document, version: DocumentVersion | None = None) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        repository_id=document.repository_id,
        display_name=document.display_name,
        current_version_id=document.current_version_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
        current_version=_version_read(version) if version is not None else None,
    )


def _version_read(version: DocumentVersion) -> DocumentVersionRead:
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
        metadata=version.extra_metadata,
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
