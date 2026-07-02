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
from private_rag.ingestion.schemas import ParsedDocument, ParsedSegment
from private_rag.ingestion.service import (
    _chunk_parsed_document,
    _coalesce_segments,
    _safe_filename,
    _write_source_file,
    delete_document,
    inspect_document,
    list_documents,
    reprocess_document,
    upload_document,
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
    Path(uploaded.version.storage_path).write_bytes(b"Summary\nsecond version\nwith more content\n")

    inspection = reprocess_document(session, repository_id, uploaded.document.id)

    assert inspection is not None
    assert inspection.version.status == "parsed"
    assert inspection.version.chunk_count == len(inspection.chunks)
    assert "second version" in inspection.chunks[0].text


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
    Path(uploaded.version.storage_path).unlink()

    inspection = reprocess_document(session, repository_id, uploaded.document.id)

    assert inspection is not None
    assert inspection.version.status == "failed"
    assert "Original source file is missing." in inspection.version.warnings


def test_upload_parser_exception_creates_failed_inspectable_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = next(_session())
    repository_id = _repository_id(session, tmp_path)

    def broken_parser(filename: str, content_type: str | None, data: bytes) -> ParsedDocument:
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
