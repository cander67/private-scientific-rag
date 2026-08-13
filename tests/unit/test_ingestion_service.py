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
from private_rag.ingestion.parser import ParserExecutionSettings, parse_source
from private_rag.ingestion.schemas import ParsedDocument, ParsedSegment
from private_rag.ingestion.service import (
    _chunk_parsed_document,
    _coalesce_segments,
    _fixed_size_segments,
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
from private_rag.ingestion.tokenizers import (
    ResolvedTokenizer,
    SimpleTokenFallbackTokenizer,
    TokenizerMetadata,
)
from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import (
    DEFAULT_CHUNK_OVERLAP_TOKENS,
    DEFAULT_CHUNK_SIZE_TOKENS,
    RepositorySettings,
)
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


def _resolved_calibration_tokenizer() -> ResolvedTokenizer:
    return ResolvedTokenizer(
        tokenizer=SimpleTokenFallbackTokenizer(),
        metadata=TokenizerMetadata(
            provider="private_rag",
            tokenizer_id="private-rag/simple-token-fallback-v1",
            tokenizer_name="private-rag/simple-token-fallback-v1",
            tokenizer_source="calibration_fixture",
            implementation_library="regex",
            precision="fallback",
            selection_mode="auto",
            offset_mapping=True,
            is_fallback=True,
            fallback_reason="deterministic fixture test",
        ),
    )


def _token_series(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}_{index:03d}" for index in range(count))


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
    assert len(coalesced) == 1
    assert coalesced[-1].metadata["sections"] == ["A", "B"]


def test_recursive_coalescing_respects_token_budget_and_overlap() -> None:
    tokenizer = SimpleTokenFallbackTokenizer()
    chunks = _coalesce_segments(
        [
            ParsedSegment(text="alpha beta", section="A", line_start=1, line_end=1),
            ParsedSegment(text="gamma delta", section="B", line_start=2, line_end=2),
            ParsedSegment(text="epsilon zeta", section="C", line_start=3, line_end=3),
        ],
        chunk_size=5,
        chunk_overlap=2,
        tokenizer=tokenizer,
    )

    assert [chunk.metadata["token_count"] for chunk in chunks] == [4, 4]
    assert chunks[0].text == "alpha beta\ngamma delta"
    assert chunks[1].text == "gamma delta\nepsilon zeta"
    assert chunks[0].metadata["sections"] == ["A", "B"]
    assert chunks[1].metadata["sections"] == ["B", "C"]


def test_recursive_coalescing_splits_oversized_segments_by_token_window() -> None:
    tokenizer = SimpleTokenFallbackTokenizer()
    text = "one two\nthree four five six seven"
    chunks = _coalesce_segments(
        [
            ParsedSegment(
                text=text,
                section="Long",
                line_start=10,
                line_end=11,
                char_start=100,
                char_end=100 + len(text),
            )
        ],
        chunk_size=3,
        chunk_overlap=1,
        tokenizer=tokenizer,
    )

    assert [chunk.text for chunk in chunks] == [
        "one two\nthree",
        "three four five",
        "five six seven",
    ]
    assert all(chunk.metadata["oversized_segment_split"] for chunk in chunks)
    assert all(chunk.metadata["token_count"] <= 3 for chunk in chunks)
    assert [(chunk.line_start, chunk.line_end) for chunk in chunks] == [
        (10, 11),
        (11, 11),
        (11, 11),
    ]
    assert [(chunk.char_start, chunk.char_end) for chunk in chunks] == [
        (100, 113),
        (108, 123),
        (119, 133),
    ]


def test_recursive_chunk_creation_records_token_metadata_and_source_fields() -> None:
    tokenizer = SimpleTokenFallbackTokenizer()
    resolved = ResolvedTokenizer(
        tokenizer=tokenizer,
        metadata=TokenizerMetadata(
            provider="private_rag",
            tokenizer_id="fake",
            tokenizer_name="fake",
            tokenizer_source="test",
            implementation_library="regex",
            precision="fallback",
            selection_mode="manual",
            offset_mapping=True,
            is_fallback=True,
            fallback_reason="unit test",
        ),
    )

    chunks = _chunk_parsed_document(
        parsed=ParsedDocument(
            source_type="text",
            text="",
            parser_name="test-parser",
            parser_version="test-v1",
            segments=[
                ParsedSegment(
                    text="alpha beta gamma delta epsilon",
                    section="A",
                    line_start=1,
                    line_end=1,
                    char_start=0,
                    char_end=30,
                    metadata={"parser_segment_id": "seg-1"},
                )
            ],
            metadata={"parser_fingerprint": "abc123", "parser_route": ["test"]},
        ),
        repository_id="repo",
        document_id="doc",
        document_version_id="version",
        chunking_mode="recursive",
        chunk_size=3,
        chunk_overlap=1,
        source_hash="hash",
        parser_version="test-v1",
        resolved_tokenizer=resolved,
    )

    assert len(chunks) == 2
    assert all(chunk.extra_metadata["chunking"]["chunk_unit"] == "tokens" for chunk in chunks)
    assert all(chunk.extra_metadata["token_count"] <= 3 for chunk in chunks)
    assert chunks[0].extra_metadata["tokenizer"] == {
        "provider": "private_rag",
        "tokenizer_id": "fake",
        "tokenizer_name": "fake",
        "tokenizer_source": "test",
        "implementation_library": "regex",
        "precision": "fallback",
        "selection_mode": "manual",
        "offset_mapping": True,
        "is_fallback": True,
        "fallback_reason": "unit test",
    }
    assert chunks[0].extra_metadata["source_hash"] == "hash"
    assert chunks[0].extra_metadata["parser_fingerprint"] == "abc123"


def test_default_token_chunking_settings_are_calibrated() -> None:
    settings = RepositorySettings.from_app_settings(Settings())

    assert settings.chunking.chunk_unit == "tokens"
    assert settings.chunking.chunk_size == DEFAULT_CHUNK_SIZE_TOKENS
    assert settings.chunking.chunk_overlap == DEFAULT_CHUNK_OVERLAP_TOKENS
    assert DEFAULT_CHUNK_SIZE_TOKENS == 512
    assert DEFAULT_CHUNK_OVERLAP_TOKENS == 64


@pytest.mark.parametrize(
    ("fixture_path", "filename", "content_type", "expected_source_type", "expected_phrase"),
    [
        (
            "tests/fixtures/ingestion/materials-synthesis-procedure.txt",
            "materials-synthesis-procedure.txt",
            "text/plain",
            "text",
            "pale yellow crystals",
        ),
        (
            "tests/fixtures/ingestion/dataset-readme.md",
            "dataset-readme.md",
            "text/markdown",
            "markdown",
            "BRAT standoff annotations",
        ),
    ],
)
def test_default_token_chunking_keeps_small_committed_fixtures_readable(
    fixture_path: str,
    filename: str,
    content_type: str,
    expected_source_type: str,
    expected_phrase: str,
) -> None:
    settings = RepositorySettings.from_app_settings(Settings())
    parsed = parse_source(filename, content_type, Path(fixture_path).read_bytes())
    resolved = _resolved_calibration_tokenizer()

    chunks = _chunk_parsed_document(
        parsed=parsed,
        repository_id="repo",
        document_id="doc",
        document_version_id="version",
        chunking_mode=settings.chunking.mode,
        chunk_size=settings.chunking.chunk_size,
        chunk_overlap=settings.chunking.chunk_overlap,
        source_hash="hash",
        parser_version=parsed.parser_version,
        resolved_tokenizer=resolved,
    )

    assert parsed.source_type == expected_source_type
    assert len(chunks) == 1
    assert expected_phrase in chunks[0].text
    assert chunks[0].extra_metadata["chunking"] == {
        "chunking_mode": "recursive",
        "chunk_size": DEFAULT_CHUNK_SIZE_TOKENS,
        "chunk_overlap": DEFAULT_CHUNK_OVERLAP_TOKENS,
        "chunk_unit": "tokens",
    }
    assert chunks[0].extra_metadata["token_count"] < DEFAULT_CHUNK_SIZE_TOKENS


def test_default_token_chunking_coalesces_parser_segments_without_flattening_sections() -> None:
    settings = RepositorySettings.from_app_settings(Settings())
    parsed = ParsedDocument(
        source_type="text",
        text="",
        parser_name="calibration-parser",
        parser_version="test-v1",
        segments=[
            ParsedSegment(
                text=_token_series("abstract_alpha", 140),
                section="Abstract",
                line_start=1,
                line_end=3,
            ),
            ParsedSegment(
                text=_token_series("method_beta", 140),
                section="Methods",
                line_start=4,
                line_end=8,
            ),
            ParsedSegment(
                text=_token_series("results_gamma", 140),
                section="Results",
                line_start=9,
                line_end=13,
            ),
            ParsedSegment(
                text=_token_series("discussion_delta", 140),
                section="Discussion",
                line_start=14,
                line_end=18,
            ),
        ],
    )

    chunks = _chunk_parsed_document(
        parsed=parsed,
        repository_id="repo",
        document_id="doc",
        document_version_id="version",
        chunking_mode=settings.chunking.mode,
        chunk_size=settings.chunking.chunk_size,
        chunk_overlap=settings.chunking.chunk_overlap,
        source_hash="hash",
        parser_version=parsed.parser_version,
        resolved_tokenizer=_resolved_calibration_tokenizer(),
    )

    assert len(chunks) == 2
    assert chunks[0].text.startswith("abstract_alpha_000")
    assert chunks[0].section == "Results"
    assert chunks[1].text.startswith("discussion_delta_000")
    assert chunks[1].section == "Discussion"
    assert [chunk.extra_metadata["token_count"] for chunk in chunks] == [420, 140]
    assert all(
        chunk.extra_metadata["chunking"]["chunk_size"] == DEFAULT_CHUNK_SIZE_TOKENS
        for chunk in chunks
    )


def test_default_token_chunking_splits_ocr_like_long_block_into_readable_windows() -> None:
    settings = RepositorySettings.from_app_settings(Settings())
    text = Path("tests/fixtures/ingestion/ocr-like-long-block.txt").read_text()
    parsed = ParsedDocument(
        source_type="pdf",
        text=text,
        parser_name="ocr-calibration",
        parser_version="test-v1",
        segments=[
            ParsedSegment(
                text=text,
                section="OCR recovered text",
                page_start=1,
                page_end=16,
                line_start=1,
                line_end=16,
                char_start=0,
                char_end=len(text),
                metadata={"ocr_derived": True},
            )
        ],
    )

    chunks = _chunk_parsed_document(
        parsed=parsed,
        repository_id="repo",
        document_id="doc",
        document_version_id="version",
        chunking_mode=settings.chunking.mode,
        chunk_size=settings.chunking.chunk_size,
        chunk_overlap=settings.chunking.chunk_overlap,
        source_hash="hash",
        parser_version=parsed.parser_version,
        resolved_tokenizer=_resolved_calibration_tokenizer(),
    )

    assert len(chunks) == 2
    assert chunks[0].text.startswith("OCR page 1 recovered")
    assert chunks[1].text.startswith("and the final note warns")
    assert chunks[1].text.endswith(
        "reproducibility context, and the extracted text preserves enough sequence detail for chunk calibration."
    )
    assert [chunk.extra_metadata["token_count"] for chunk in chunks] == [512, 190]
    assert chunks[0].extra_metadata["token_window_start"] == 0
    assert chunks[0].extra_metadata["token_window_end"] == DEFAULT_CHUNK_SIZE_TOKENS
    assert chunks[1].extra_metadata["token_window_start"] == 448
    assert chunks[1].extra_metadata["chunking"]["chunk_overlap"] == DEFAULT_CHUNK_OVERLAP_TOKENS
    assert all(chunk.extra_metadata["ocr_derived"] is True for chunk in chunks)


def test_fixed_size_segments_use_token_windows_with_overlap() -> None:
    tokenizer = SimpleTokenFallbackTokenizer()
    parsed = ParsedDocument(
        source_type="text",
        text="  alpha beta gamma\ndelta epsilon zeta eta  ",
    )

    chunks = _fixed_size_segments(parsed, chunk_size=3, chunk_overlap=1, tokenizer=tokenizer)

    assert [chunk.text for chunk in chunks] == [
        "alpha beta gamma",
        "gamma\ndelta epsilon",
        "epsilon zeta eta",
    ]
    assert [chunk.metadata["token_window_start"] for chunk in chunks] == [0, 2, 4]
    assert [chunk.metadata["token_window_end"] for chunk in chunks] == [3, 5, 7]
    assert [chunk.metadata["token_count"] for chunk in chunks] == [3, 3, 3]
    assert [(chunk.line_start, chunk.line_end) for chunk in chunks] == [(1, 1), (1, 2), (2, 2)]
    assert [(chunk.char_start, chunk.char_end) for chunk in chunks] == [
        (2, 18),
        (13, 32),
        (25, 41),
    ]


def test_fixed_size_segments_create_final_short_chunk_and_skip_empty_text() -> None:
    tokenizer = SimpleTokenFallbackTokenizer()

    chunks = _fixed_size_segments(
        ParsedDocument(source_type="text", text="alpha beta gamma delta"),
        chunk_size=3,
        chunk_overlap=0,
        tokenizer=tokenizer,
    )

    assert [chunk.text for chunk in chunks] == ["alpha beta gamma", "delta"]
    assert [chunk.metadata["token_count"] for chunk in chunks] == [3, 1]
    assert (
        _fixed_size_segments(
            ParsedDocument(source_type="text", text="   \n\t"),
            chunk_size=3,
            chunk_overlap=1,
            tokenizer=tokenizer,
        )
        == []
    )


def test_fixed_chunk_creation_records_token_window_metadata() -> None:
    tokenizer = SimpleTokenFallbackTokenizer()
    resolved = ResolvedTokenizer(
        tokenizer=tokenizer,
        metadata=TokenizerMetadata(
            provider="private_rag",
            tokenizer_id="fake-fixed",
            tokenizer_name="fake-fixed",
            tokenizer_source="test",
            implementation_library="regex",
            precision="fallback",
            selection_mode="manual",
            offset_mapping=True,
            is_fallback=True,
        ),
    )

    chunks = _chunk_parsed_document(
        parsed=ParsedDocument(
            source_type="text",
            text="alpha beta gamma delta epsilon",
            parser_name="test-parser",
            parser_version="test-v1",
            metadata={"parser_fingerprint": "fixed-fingerprint"},
        ),
        repository_id="repo",
        document_id="doc",
        document_version_id="version",
        chunking_mode="fixed",
        chunk_size=3,
        chunk_overlap=1,
        source_hash="hash",
        parser_version="test-v1",
        resolved_tokenizer=resolved,
    )

    assert [chunk.text for chunk in chunks] == [
        "alpha beta gamma",
        "gamma delta epsilon",
    ]
    assert [chunk.extra_metadata["token_count"] for chunk in chunks] == [3, 3]
    assert chunks[1].extra_metadata["token_window_start"] == 2
    assert chunks[1].extra_metadata["token_window_end"] == 5
    assert "fixed_window_start" not in chunks[0].extra_metadata
    assert chunks[0].extra_metadata["tokenizer"]["tokenizer_name"] == "fake-fixed"
    assert chunks[0].extra_metadata["parser_fingerprint"] == "fixed-fingerprint"
    assert chunks[0].extra_metadata["source_hash"] == "hash"


def test_upload_uses_fixed_chunking_mode_for_token_windows(tmp_path: Path) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)
    repository = session.get(Repository, repository_id)
    assert repository is not None
    assert repository.settings is not None
    settings = RepositorySettings.model_validate(repository.settings.settings)
    settings.chunking.mode = "fixed"
    settings.chunking.chunk_size = 100
    settings.chunking.chunk_overlap = 25
    settings.embedding.provider = "ollama"
    settings.embedding.model = "custom-local:latest"
    settings.vector.vector_size = 768
    settings.vector.distance = "cosine"
    repository.settings.settings = settings.model_dump(mode="json")
    session.add(repository.settings)
    session.commit()

    uploaded = upload_document(
        session,
        repository_id,
        "fixed.txt",
        "text/plain",
        ("alpha " * 120 + "\n" + "beta " * 120).encode(),
        settings=Settings(data_dir=tmp_path),
    )

    assert uploaded is not None
    assert uploaded.version.chunk_count >= 2
    first_chunk = uploaded.chunks_preview[0]
    second_chunk = uploaded.chunks_preview[1]
    assert first_chunk.metadata["token_count"] <= 100
    assert second_chunk.metadata["token_window_start"] == 75
    assert first_chunk.metadata["chunking"] == {
        "chunking_mode": "fixed",
        "chunk_size": 100,
        "chunk_overlap": 25,
        "chunk_unit": "tokens",
    }
    assert first_chunk.metadata["tokenizer"]["precision"] == "fallback"
    assert first_chunk.metadata["tokenizer"]["tokenizer_name"]
    assert "token_window_start" in first_chunk.metadata
    assert "fixed_window_start" not in first_chunk.metadata


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
        "chunk_unit": "tokens",
    }
    assert first_chunk.metadata["tokenizer"]["precision"] in {"exact", "fallback"}
    assert first_chunk.metadata["tokenizer"]["tokenizer_name"]
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
    assert payload["chunking"]["chunk_unit"] == "tokens"
    assert payload["tokenizer"]["tokenizer_name"]
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
    assert unchanged.chunks[0].metadata["chunking"]["chunk_unit"] == "tokens"
    assert unchanged.chunks[0].metadata["token_count"] > 0
    assert unchanged.chunks[0].metadata["tokenizer"]["tokenizer_name"]

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
    assert changed.chunks[0].metadata["chunking"]["chunk_unit"] == "tokens"


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
