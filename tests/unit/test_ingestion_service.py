from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.core.settings import Settings
from private_rag.db.base import Base
from private_rag.ingestion import service as ingestion_service
from private_rag.ingestion.models import Document
from private_rag.ingestion.ocr import (
    NormalizedOcrPageResult,
    OcrPageImage,
    normalize_ocr_page_result,
)
from private_rag.ingestion.parser import ParserExecutionSettings
from private_rag.ingestion.schemas import ParsedDocument, ParsedSegment
from private_rag.ingestion.service import (
    _chunk_parsed_document,
    _coalesce_segments,
    _safe_filename,
    _write_source_file,
    delete_document,
    inspect_document,
    inspect_document_version,
    list_documents,
    reprocess_document,
    run_document_ocr,
    upload_document,
)
from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import RepositorySettings
from private_rag.repositories.service import ensure_default_repository


def _session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    with session_factory() as session:
        yield session


def _repository_id(session: Session, tmp_path: Path) -> str:
    settings = Settings(data_dir=tmp_path, database_url="sqlite:///:memory:")
    return ensure_default_repository(session, settings=settings).repository.id


class FakeOcrProvider:
    provider_name = "synthetic_ocr"
    provider_version = "test-v1"

    def recognize_page(self, image: OcrPageImage) -> NormalizedOcrPageResult:
        return normalize_ocr_page_result(
            page=image.page,
            text=f"OCR recovered text for page {image.page}",
            confidence=0.93,
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            image=image,
        )


class LowQualityOcrProvider:
    provider_name = "ocrmypdf_tesseract"
    provider_version = "test-low"

    def recognize_page(self, image: OcrPageImage) -> NormalizedOcrPageResult:
        return normalize_ocr_page_result(
            page=image.page,
            text="low",
            confidence=0.2,
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            image=image,
        )


class FallbackOcrProvider:
    provider_name = "rapidocr"
    provider_version = "test-fallback"

    def recognize_page(self, image: OcrPageImage) -> NormalizedOcrPageResult:
        return normalize_ocr_page_result(
            page=image.page,
            text=f"RapidOCR fallback text for page {image.page}",
            confidence=0.91,
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            image=image,
        )


def test_upload_returns_none_for_missing_repository(tmp_path: Path) -> None:
    session = next(_session())

    uploaded = upload_document(
        session=session,
        repository_id="missing",
        filename="notes.txt",
        content_type="text/plain",
        data=b"hello\n",
        settings=Settings(data_dir=tmp_path),
    )

    assert uploaded is None


def test_duplicate_upload_is_reported_as_skipped(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    settings = Settings(data_dir=tmp_path)

    first = upload_document(
        session,
        repository_id,
        "notes.txt",
        "text/plain",
        b"same text\n",
        settings=settings,
    )
    second = upload_document(
        session,
        repository_id,
        "notes.txt",
        "text/plain",
        b"same text\n",
        settings=settings,
    )

    assert first is not None
    assert second is not None
    assert second.version.status == "skipped"
    assert second.document.id == first.document.id


def test_list_inspect_and_delete_missing_documents_return_none(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    other_document = Document(repository_id="other", display_name="other.txt")
    session.add(other_document)
    session.commit()

    assert list_documents(session, "missing") is None
    assert inspect_document(session, repository_id, "missing") is None
    assert inspect_document(session, repository_id, other_document.id) is None
    assert delete_document(session, repository_id, "missing") is None
    assert delete_document(session, repository_id, other_document.id) is None


def test_inspect_document_without_version_returns_none(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    document = Document(repository_id=repository_id, display_name="empty.txt")
    session.add(document)
    session.commit()

    assert inspect_document(session, repository_id, document.id) is None


def test_reprocess_document_updates_chunks_from_stored_source(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    uploaded = upload_document(
        session,
        repository_id,
        "notes.txt",
        "text/plain",
        b"Abstract\nfirst version\n",
        settings=Settings(data_dir=tmp_path),
    )
    assert uploaded is not None
    first_version_id = uploaded.version.id
    Path(uploaded.version.storage_path).write_bytes(b"Summary\nsecond version\nwith more content\n")

    inspection = reprocess_document(session, repository_id, uploaded.document.id)
    prior_inspection = inspect_document_version(
        session,
        repository_id,
        uploaded.document.id,
        first_version_id,
    )

    assert inspection is not None
    assert prior_inspection is not None
    assert inspection.version.id != first_version_id
    assert inspection.document.current_version_id == inspection.version.id
    assert inspection.version.status == "parsed"
    assert inspection.version.chunk_count == len(inspection.chunks)
    assert "second version" in inspection.chunks[0].text
    assert "first version" in prior_inspection.chunks[0].text
    assert inspection.version.metadata["reprocess"]["source_version_id"] == first_version_id


def test_run_document_ocr_adds_page_artifacts_and_ocr_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(
        ingestion_service,
        "parse_source",
        lambda *args, **kwargs: ParsedDocument(
            source_type="pdf",
            text="",
            parser_name="pypdf",
            parser_version="test-parser",
            page_count=1,
            ocr_required=True,
            metadata={
                "page_ocr_routes": [
                    {
                        "page": 1,
                        "classification": "scanned",
                        "text_length": 0,
                        "word_count": 0,
                        "image_count": 1,
                        "quality_score": 0.1,
                        "needs_ocr": True,
                        "warnings": ["Page appears image-only and is pending OCR."],
                    }
                ],
                "ocr_status": {
                    "status": "pending",
                    "pages_pending": [1],
                    "pages_routed": 1,
                    "warnings": [],
                },
            },
        ),
    )
    fake_image = OcrPageImage(
        page=1,
        path=str(tmp_path / "ocr-page-0001.png"),
        mime_type="image/png",
        width=100,
        height=120,
        byte_size=5,
        sha256="image-hash",
        renderer="pymupdf",
        source_sha256="source-hash",
    )
    monkeypatch.setattr(
        ingestion_service,
        "render_pages_for_ocr",
        lambda **kwargs: ([fake_image], []),
    )
    uploaded = upload_document(
        session,
        repository_id,
        "scan.pdf",
        "application/pdf",
        b"%PDF scan",
        settings=settings,
    )

    assert uploaded is not None
    inspection = run_document_ocr(
        session,
        repository_id,
        uploaded.document.id,
        provider=FakeOcrProvider(),
        settings=settings,
    )

    assert inspection is not None
    assert inspection.version.status == "parsed"
    assert inspection.version.ocr_required is False
    assert inspection.version.metadata["ocr_run"]["status"] == "completed"
    assert inspection.version.metadata["ocr_pages"][0]["text"] == "OCR recovered text for page 1"
    assert inspection.chunks[0].text == "OCR recovered text for page 1"
    assert inspection.chunks[0].section == "ocr"
    assert inspection.chunks[0].metadata["ocr_derived"] is True
    assert inspection.chunks[0].metadata["ocr_provider"]["name"] == "synthetic_ocr"
    assert inspection.chunks[0].metadata["ocr_confidence"] == 0.93
    assert inspection.chunks[0].metadata["page_provenance"]["image_sha256"] == "image-hash"


def test_run_document_ocr_missing_provider_preserves_prior_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(
        ingestion_service,
        "parse_source",
        lambda *args, **kwargs: ParsedDocument(
            source_type="pdf",
            text="",
            parser_name="pypdf",
            parser_version="test-parser",
            page_count=1,
            ocr_required=True,
            metadata={
                "page_ocr_routes": [
                    {
                        "page": 1,
                        "classification": "scanned",
                        "text_length": 0,
                        "word_count": 0,
                        "image_count": 1,
                        "quality_score": 0.1,
                        "needs_ocr": True,
                        "warnings": [],
                    }
                ]
            },
        ),
    )
    fake_image = OcrPageImage(
        page=1,
        path=str(tmp_path / "ocr-page-0001.png"),
        mime_type="image/png",
        width=100,
        height=120,
        byte_size=5,
        sha256="image-hash",
        renderer="pymupdf",
        source_sha256="source-hash",
    )
    monkeypatch.setattr(
        ingestion_service,
        "render_pages_for_ocr",
        lambda **kwargs: ([fake_image], []),
    )
    monkeypatch.setattr(ingestion_service, "default_ocr_provider", lambda *args, **kwargs: None)
    uploaded = upload_document(
        session,
        repository_id,
        "scan.pdf",
        "application/pdf",
        b"%PDF scan",
        settings=settings,
    )

    assert uploaded is not None
    inspection = run_document_ocr(
        session,
        repository_id,
        uploaded.document.id,
        settings=settings,
    )

    assert inspection is not None
    assert inspection.version.status == "needs_ocr"
    assert inspection.version.ocr_required is True
    assert inspection.version.chunk_count == 0
    assert inspection.version.metadata["ocr_run"]["status"] == "missing_dependency"
    assert inspection.version.metadata["ocr_pages"][0]["provider"]["version"] == "not-installed"
    assert (
        "ocrmypdf_tesseract is not installed; OCR is pending for page 1."
        in inspection.version.warnings
    )


def test_run_document_ocr_uses_fallback_when_quality_is_low(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(
        ingestion_service,
        "parse_source",
        lambda *args, **kwargs: ParsedDocument(
            source_type="pdf",
            text="",
            parser_name="pypdf",
            parser_version="test-parser",
            page_count=1,
            ocr_required=True,
            metadata={
                "page_ocr_routes": [
                    {
                        "page": 1,
                        "classification": "scanned",
                        "text_length": 0,
                        "word_count": 0,
                        "image_count": 1,
                        "quality_score": 0.1,
                        "needs_ocr": True,
                        "warnings": [],
                    }
                ]
            },
        ),
    )
    fake_image = OcrPageImage(
        page=1,
        path=str(tmp_path / "ocr-page-0001.png"),
        mime_type="image/png",
        width=100,
        height=120,
        byte_size=5,
        sha256="image-hash",
        renderer="pymupdf",
        source_sha256="source-hash",
    )
    monkeypatch.setattr(
        ingestion_service,
        "render_pages_for_ocr",
        lambda **kwargs: ([fake_image], []),
    )
    uploaded = upload_document(
        session,
        repository_id,
        "scan.pdf",
        "application/pdf",
        b"%PDF scan",
        settings=settings,
    )

    assert uploaded is not None
    inspection = run_document_ocr(
        session,
        repository_id,
        uploaded.document.id,
        provider=LowQualityOcrProvider(),
        fallback_provider=FallbackOcrProvider(),
        settings=settings,
    )

    assert inspection is not None
    assert inspection.chunks[0].text == "RapidOCR fallback text for page 1"
    assert inspection.chunks[0].metadata["ocr_provider"]["name"] == "rapidocr"
    decision = inspection.version.metadata["ocr_run"]["fallback_decisions"][0]
    assert decision["status"] == "used"
    assert decision["reason"] == "min_text_length"
    assert decision["fallback_provider"] == "rapidocr"


def test_run_document_ocr_skips_fallback_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    repository = session.get(Repository, repository_id)
    assert repository is not None
    assert repository.settings is not None
    repository_settings = RepositorySettings.model_validate(repository.settings.settings)
    repository_settings.ocr.fallback_enabled = False
    repository.settings.settings = repository_settings.model_dump(mode="json")
    session.add(repository.settings)
    session.commit()

    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(
        ingestion_service,
        "parse_source",
        lambda *args, **kwargs: ParsedDocument(
            source_type="pdf",
            text="",
            parser_name="pypdf",
            parser_version="test-parser",
            page_count=1,
            ocr_required=True,
            metadata={
                "page_ocr_routes": [
                    {
                        "page": 1,
                        "classification": "scanned",
                        "text_length": 0,
                        "word_count": 0,
                        "image_count": 1,
                        "quality_score": 0.1,
                        "needs_ocr": True,
                        "warnings": [],
                    }
                ]
            },
        ),
    )
    fake_image = OcrPageImage(
        page=1,
        path=str(tmp_path / "ocr-page-0001.png"),
        mime_type="image/png",
        width=100,
        height=120,
        byte_size=5,
        sha256="image-hash",
        renderer="pymupdf",
        source_sha256="source-hash",
    )
    monkeypatch.setattr(
        ingestion_service,
        "render_pages_for_ocr",
        lambda **kwargs: ([fake_image], []),
    )
    uploaded = upload_document(
        session,
        repository_id,
        "scan.pdf",
        "application/pdf",
        b"%PDF scan",
        settings=settings,
    )

    assert uploaded is not None
    inspection = run_document_ocr(
        session,
        repository_id,
        uploaded.document.id,
        provider=LowQualityOcrProvider(),
        fallback_provider=FallbackOcrProvider(),
        settings=settings,
    )

    assert inspection is not None
    assert inspection.chunks[0].text == "low"
    assert inspection.chunks[0].metadata["ocr_provider"]["name"] == "ocrmypdf_tesseract"
    assert inspection.version.metadata["ocr_run"]["fallback_decisions"] == []


def test_run_document_ocr_records_missing_fallback_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(
        ingestion_service,
        "parse_source",
        lambda *args, **kwargs: ParsedDocument(
            source_type="pdf",
            text="",
            parser_name="pypdf",
            parser_version="test-parser",
            page_count=1,
            ocr_required=True,
            metadata={
                "page_ocr_routes": [
                    {
                        "page": 1,
                        "classification": "scanned",
                        "text_length": 0,
                        "word_count": 0,
                        "image_count": 1,
                        "quality_score": 0.1,
                        "needs_ocr": True,
                        "warnings": [],
                    }
                ]
            },
        ),
    )
    fake_image = OcrPageImage(
        page=1,
        path=str(tmp_path / "ocr-page-0001.png"),
        mime_type="image/png",
        width=100,
        height=120,
        byte_size=5,
        sha256="image-hash",
        renderer="pymupdf",
        source_sha256="source-hash",
    )
    monkeypatch.setattr(
        ingestion_service,
        "render_pages_for_ocr",
        lambda **kwargs: ([fake_image], []),
    )
    monkeypatch.setattr(ingestion_service, "default_ocr_provider", lambda *args, **kwargs: None)
    uploaded = upload_document(
        session,
        repository_id,
        "scan.pdf",
        "application/pdf",
        b"%PDF scan",
        settings=settings,
    )

    assert uploaded is not None
    inspection = run_document_ocr(
        session,
        repository_id,
        uploaded.document.id,
        provider=LowQualityOcrProvider(),
        settings=settings,
    )

    assert inspection is not None
    assert inspection.chunks[0].text == "low"
    decision = inspection.version.metadata["ocr_run"]["fallback_decisions"][0]
    assert decision["status"] == "missing_dependency"
    assert (
        "rapidocr is not installed; OCR fallback skipped for page 1." in inspection.version.warnings
    )


def test_reprocess_document_reports_missing_source_file(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    uploaded = upload_document(
        session,
        repository_id,
        "notes.txt",
        "text/plain",
        b"Abstract\nfirst version\n",
        settings=Settings(data_dir=tmp_path),
    )
    assert uploaded is not None
    first_version_id = uploaded.version.id
    Path(uploaded.version.storage_path).unlink()

    inspection = reprocess_document(session, repository_id, uploaded.document.id)
    prior_inspection = inspect_document_version(
        session,
        repository_id,
        uploaded.document.id,
        first_version_id,
    )

    assert inspection is not None
    assert prior_inspection is not None
    assert inspection.version.id != first_version_id
    assert inspection.version.status == "failed"
    assert "Original source file is missing." in inspection.version.warnings
    assert inspection.version.metadata["reprocess"]["source_version_id"] == first_version_id


def test_upload_parser_exception_creates_failed_inspectable_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)

    def broken_parser(
        filename: str,
        content_type: str | None,
        data: bytes,
        **kwargs: object,
    ) -> ParsedDocument:
        raise RuntimeError("parser boom")

    monkeypatch.setattr(ingestion_service, "parse_source", broken_parser)

    uploaded = upload_document(
        session,
        repository_id,
        "paper.txt",
        "text/plain",
        b"unparseable",
        settings=Settings(data_dir=tmp_path),
    )

    assert uploaded is not None
    assert uploaded.version.status == "failed"
    assert uploaded.version.chunk_count == 0
    assert uploaded.version.metadata["parse_error"] == "RuntimeError"
    assert "Parsing failed: RuntimeError: parser boom" in uploaded.version.warnings


def test_reprocess_missing_and_wrong_repository_return_none(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    uploaded = upload_document(
        session,
        repository_id,
        "notes.txt",
        "text/plain",
        b"Abstract\nfirst version\n",
        settings=Settings(data_dir=tmp_path),
    )
    assert uploaded is not None

    assert reprocess_document(session, repository_id, "missing") is None
    assert reprocess_document(session, "other", uploaded.document.id) is None


def test_reprocess_document_without_version_returns_none(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    document = Document(repository_id=repository_id, display_name="empty.txt")
    session.add(document)
    session.commit()

    assert reprocess_document(session, repository_id, document.id) is None


def test_helper_storage_and_chunk_edges(tmp_path: Path) -> None:
    written = _write_source_file(
        repository_id="repo",
        filename="bad/name?.txt",
        digest="abcdef1234567890",
        data=b"hello",
        settings=Settings(data_dir=tmp_path),
    )
    blank_chunks = _chunk_parsed_document(
        parsed=ParsedDocument(
            source_type="text",
            text=" ",
            segments=[ParsedSegment(text="   ")],
        ),
        repository_id="repo",
        document_id="doc",
        document_version_id="version",
        chunking_mode="recursive",
        chunk_size=100,
        chunk_overlap=0,
        source_hash="hash",
        parser_version="test-parser",
    )
    coalesced = _coalesce_segments(
        [
            ParsedSegment(text="alpha", section="A", line_start=1, line_end=1),
            ParsedSegment(text="beta", section="B", line_start=2, line_end=2),
            ParsedSegment(text="gamma", section="B", line_start=3, line_end=3),
        ],
        chunk_size=12,
        chunk_overlap=6,
    )

    assert written.read_bytes() == b"hello"
    assert written.name == "abcdef123456-name-.txt"
    assert _safe_filename("///") == "document"
    assert blank_chunks == []
    assert len(coalesced) >= 2
    assert coalesced[-1].metadata["sections"] == ["B"]


def test_upload_uses_fixed_chunking_mode_for_fixed_size_windows(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    repository = session.get(Repository, repository_id)
    assert repository is not None
    assert repository.settings is not None
    settings = RepositorySettings.model_validate(repository.settings.settings)
    settings.chunking.mode = "fixed"
    settings.chunking.chunk_size = 100
    settings.chunking.chunk_overlap = 10
    repository.settings.settings = settings.model_dump(mode="json")
    session.add(repository.settings)
    session.commit()

    uploaded = upload_document(
        session,
        repository_id,
        "fixed.txt",
        "text/plain",
        ("alpha " * 20 + "\n" + "beta " * 20).encode(),
        settings=Settings(data_dir=tmp_path),
    )

    assert uploaded is not None
    assert uploaded.version.chunk_count >= 2
    first_chunk = uploaded.chunks_preview[0]
    second_chunk = uploaded.chunks_preview[1]
    assert len(first_chunk.text) <= 100
    assert second_chunk.char_start == 90
    assert first_chunk.metadata["chunking"] == {
        "chunking_mode": "fixed",
        "chunk_size": 100,
        "chunk_overlap": 10,
    }
    assert "fixed_window_start" in first_chunk.metadata


def test_upload_recursive_chunking_preserves_segment_coalescing(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    repository = session.get(Repository, repository_id)
    assert repository is not None
    assert repository.settings is not None
    settings = RepositorySettings.model_validate(repository.settings.settings)
    settings.chunking.mode = "recursive"
    settings.chunking.chunk_size = 100
    settings.chunking.chunk_overlap = 10
    repository.settings.settings = settings.model_dump(mode="json")
    session.add(repository.settings)
    session.commit()

    uploaded = upload_document(
        session,
        repository_id,
        "recursive.txt",
        "text/plain",
        ("alpha " * 20 + "\n" + "beta " * 20).encode(),
        settings=Settings(data_dir=tmp_path),
    )

    assert uploaded is not None
    first_chunk = uploaded.chunks_preview[0]
    assert first_chunk.char_start == 0
    assert first_chunk.metadata["chunking"] == {
        "chunking_mode": "recursive",
        "chunk_size": 100,
        "chunk_overlap": 10,
    }
    assert "fixed_window_start" not in first_chunk.metadata


def test_upload_uses_repository_parser_settings_and_records_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    repository = session.get(Repository, repository_id)
    assert repository is not None
    assert repository.settings is not None
    repository_settings = RepositorySettings.model_validate(repository.settings.settings)
    repository_settings.parser.structured_parser = "pymupdf"
    repository_settings.parser.fallback_parser = "built_in_fallback"
    repository.settings.settings = repository_settings.model_dump(mode="json")
    session.add(repository.settings)
    session.commit()

    def fake_parser(
        filename: str,
        content_type: str | None,
        data: bytes,
        **kwargs: object,
    ) -> ParsedDocument:
        parser_settings = kwargs["parser_settings"]
        assert isinstance(parser_settings, ParserExecutionSettings)
        assert parser_settings.structured_parser == "pymupdf"
        assert parser_settings.fallback_parser == "built_in_fallback"
        return ParsedDocument(
            source_type="text",
            text="Abstract\nrepository settings reached the parser",
            parser_name="pymupdf",
            parser_version="test",
            segments=[ParsedSegment(text="repository settings reached the parser")],
            metadata={
                "parser_route": ["pymupdf"],
                "parser_settings": {
                    "structured_parser": "pymupdf",
                    "fallback_parser": "built_in_fallback",
                },
                "parser_package_versions": {"pymupdf": "test"},
                "parser_quality_thresholds": {"min_text_length": 80},
            },
        )

    monkeypatch.setattr(ingestion_service, "parse_source", fake_parser)

    uploaded = upload_document(
        session,
        repository_id,
        "paper.txt",
        "text/plain",
        b"Abstract\nrepository settings reached the parser",
        settings=Settings(data_dir=tmp_path),
    )

    assert uploaded is not None
    fingerprint = uploaded.version.metadata["parser_fingerprint"]
    payload = uploaded.version.metadata["parser_fingerprint_payload"]
    assert len(fingerprint) == 64
    assert payload["parser"] == {
        "structured_parser": "pymupdf",
        "fallback_parser": "built_in_fallback",
    }
    assert payload["source_hash"] == uploaded.version.sha256
    assert uploaded.chunks_preview[0].metadata["parser_fingerprint"] == fingerprint
    assert uploaded.chunks_preview[0].metadata["parser_route"] == ["pymupdf"]


def test_document_read_reports_stale_reprocess_status_after_chunking_change(
    tmp_path: Path,
) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    uploaded = upload_document(
        session,
        repository_id,
        "notes.txt",
        "text/plain",
        b"Abstract\nchunking settings can make this parsed version stale\n",
        settings=Settings(data_dir=tmp_path),
    )
    assert uploaded is not None

    repository = session.get(Repository, repository_id)
    assert repository is not None
    assert repository.settings is not None
    settings = RepositorySettings.model_validate(repository.settings.settings)
    settings.chunking.chunk_size = 400
    repository.settings.settings = settings.model_dump(mode="json")
    session.add(repository.settings)
    session.commit()

    documents = list_documents(session, repository_id)
    inspection = inspect_document(session, repository_id, uploaded.document.id)

    assert documents is not None
    assert inspection is not None
    assert documents[0].current_version is not None
    status = documents[0].current_version.metadata["reprocess_status"]
    assert status["status"] == "stale"
    assert status["stale"] is True
    assert status["changed_fields"] == ["chunking.chunk_size"]
    assert inspection.version.metadata["reprocess_status"]["status"] == "stale"


def test_reprocess_records_unchanged_and_changed_fingerprint_paths(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    uploaded = upload_document(
        session,
        repository_id,
        "notes.txt",
        "text/plain",
        b"Abstract\nsame source can be reprocessed under changing settings\n",
        settings=Settings(data_dir=tmp_path),
    )
    assert uploaded is not None

    unchanged = reprocess_document(session, repository_id, uploaded.document.id)
    assert unchanged is not None
    assert unchanged.version.metadata["reprocess"]["fingerprint_changed"] is False
    assert unchanged.version.metadata["reprocess"]["changed_fields"] == []

    repository = session.get(Repository, repository_id)
    assert repository is not None
    assert repository.settings is not None
    settings = RepositorySettings.model_validate(repository.settings.settings)
    settings.parser.structured_parser = "built_in_fallback"
    repository.settings.settings = settings.model_dump(mode="json")
    session.add(repository.settings)
    session.commit()

    changed = reprocess_document(session, repository_id, uploaded.document.id)

    assert changed is not None
    assert changed.version.metadata["reprocess"]["fingerprint_changed"] is True
    assert changed.version.metadata["reprocess"]["changed_fields"] == ["parser.structured_parser"]


def test_reprocess_parser_failure_creates_failed_version_without_deleting_prior_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    uploaded = upload_document(
        session,
        repository_id,
        "notes.txt",
        "text/plain",
        b"Abstract\nfirst version\n",
        settings=Settings(data_dir=tmp_path),
    )
    assert uploaded is not None
    first_version_id = uploaded.version.id

    def broken_parser(
        filename: str,
        content_type: str | None,
        data: bytes,
        **kwargs: object,
    ) -> ParsedDocument:
        raise RuntimeError("parser boom")

    monkeypatch.setattr(ingestion_service, "parse_source", broken_parser)

    inspection = reprocess_document(session, repository_id, uploaded.document.id)
    prior_inspection = inspect_document_version(
        session,
        repository_id,
        uploaded.document.id,
        first_version_id,
    )

    assert inspection is not None
    assert prior_inspection is not None
    assert inspection.version.status == "failed"
    assert inspection.version.chunk_count == 0
    assert "Parsing failed: RuntimeError: parser boom" in inspection.version.warnings
    assert "first version" in prior_inspection.chunks[0].text
