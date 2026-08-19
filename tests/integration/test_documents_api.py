from __future__ import annotations

from collections.abc import Generator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.api.app import create_app
from private_rag.api.routes.repositories import get_db_session
from private_rag.core.settings import Settings
from private_rag.db.base import Base
from private_rag.ingestion import service as ingestion_service
from private_rag.ingestion.ocr import (
    NormalizedOcrPageResult,
    OcrPageImage,
    OcrProviderUnavailable,
    normalize_ocr_page_result,
)
from private_rag.ingestion.schemas import ParsedDocument
from private_rag.ingestion.service import upload_document
from private_rag.repositories.models import Repository, RepositorySettingsRow


def _client_with_database() -> TestClient:
    client, _ = _client_with_database_session_factory()
    return client


def _client_with_database_session_factory() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app), session_factory


def _pdf_bytes_with_text(text: str) -> bytes:
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = BytesIO()
    document.save(data)
    return data.getvalue()


class FakeOcrProvider:
    provider_name = "synthetic_ocr"
    provider_version = "test-v1"

    def recognize_page(self, image: OcrPageImage) -> NormalizedOcrPageResult:
        return normalize_ocr_page_result(
            page=image.page,
            text="Recovered API OCR text",
            confidence=0.88,
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            image=image,
        )


def test_upload_text_document_chunks_with_line_provenance() -> None:
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]

    response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "materials-synthesis-procedure.txt",
                b"Abstract\nMix precursor A with solvent B.\nHeat at 80 C.\n",
                "text/plain",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"]["source_type"] == "text"
    assert payload["version"]["status"] == "parsed"
    assert payload["version"]["chunk_count"] >= 1
    chunk = payload["chunks_preview"][0]
    assert chunk["repository_id"] == repository_id
    assert chunk["document_id"] == payload["document"]["id"]
    assert chunk["document_version_id"] == payload["version"]["id"]
    assert chunk["line_start"] == 1
    assert chunk["line_end"] == 3
    assert chunk["section"] == "Abstract"
    assert chunk["chunk_index"] == 0
    assert chunk["parser_version"] == payload["version"]["parser_version"]
    assert chunk["char_start"] == 0
    assert chunk["char_end"] > chunk["char_start"]
    assert chunk["source_hash"] == payload["version"]["sha256"]
    assert chunk["metadata"]["source_type"] == "text"


def test_upload_patent_pdf_marks_patent_section_hints() -> None:
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    pdf_bytes = (
        b"%PDF-1.4\n/Type /Page\n"
        b"Title: UV Curable Epoxy Acrylate Adhesive Composition\n"
        b"Abstract\nA curable adhesive composition is described.\n"
        b"Detailed Description\nExample 1 includes epoxy acrylate.\n"
        b"What is claimed is:\n1. A composition comprising resin.\n%%EOF"
    )

    response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("US11370944.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"]["source_type"] == "pdf"
    assert payload["version"]["metadata"]["document_kind"] == "patent_pdf"
    assert "claims" in payload["version"]["metadata"]["patent_section_hints"]
    assert payload["chunks_preview"][0]["page_start"] == 1


def test_upload_pdf_generates_and_serves_page_images(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRIVATE_RAG_DATA_DIR", str(tmp_path))
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    pdf_bytes = _pdf_bytes_with_text(
        "Abstract\nThis page has enough scientific text to parse and render as a thumbnail."
    )

    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("sectioned-paper.pdf", pdf_bytes, "application/pdf")},
    )

    assert upload_response.status_code == 200
    document_id = upload_response.json()["document"]["id"]
    inspection = client.get(f"/repositories/{repository_id}/documents/{document_id}")
    payload = inspection.json()
    page_images = payload["page_images"]
    image_response = client.get(page_images[0]["url"])

    assert inspection.status_code == 200
    assert page_images[0]["page"] == 1
    assert page_images[0]["byte_size"] > 0
    assert payload["version"]["metadata"]["page_images_available"] is True
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/png"


def test_run_ocr_action_adds_ocr_text_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRIVATE_RAG_DATA_DIR", str(tmp_path))
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
        ingestion_service, "render_pages_for_ocr", lambda **kwargs: ([fake_image], [])
    )
    monkeypatch.setattr(
        ingestion_service,
        "resolve_default_ocr_provider",
        lambda *args, **kwargs: (FakeOcrProvider(), None),
    )
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("scan.pdf", b"%PDF scan", "application/pdf")},
    )
    document_id = upload_response.json()["document"]["id"]

    ocr_response = client.post(f"/repositories/{repository_id}/documents/{document_id}/ocr")
    payload = ocr_response.json()

    assert upload_response.status_code == 200
    assert ocr_response.status_code == 200
    assert payload["version"]["status"] == "parsed"
    assert payload["version"]["metadata"]["ocr_run"]["status"] == "completed"
    assert payload["chunks"][0]["text"] == "Recovered API OCR text"
    assert payload["chunks"][0]["metadata"]["ocr_derived"] is True


def test_upload_markdown_and_annotation_then_inspect_and_delete() -> None:
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    markdown_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("dataset-readme.md", b"# Dataset\nText and ANN files.\n", "text/markdown")},
    )
    annotation_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "sample.ann",
                b"T1\tMaterial 0 8\tprecursor\nR1\tNext Arg1:T1 Arg2:T1\n",
                "text/plain",
            )
        },
    )

    assert markdown_response.status_code == 200
    assert annotation_response.status_code == 200
    document_id = annotation_response.json()["document"]["id"]

    inspection = client.get(f"/repositories/{repository_id}/documents/{document_id}")
    documents = client.get(f"/repositories/{repository_id}/documents")
    delete_response = client.delete(f"/repositories/{repository_id}/documents/{document_id}")
    deleted_inspection = client.get(f"/repositories/{repository_id}/documents/{document_id}")

    assert inspection.status_code == 200
    assert inspection.json()["version"]["metadata"]["annotation_format"] == "brat_standoff"
    assert len(documents.json()) == 2
    assert delete_response.status_code == 204
    assert deleted_inspection.status_code == 404


def test_reprocess_creates_new_version_and_preserves_prior_inspection() -> None:
    client = _client_with_database()
    default = client.get("/repositories/default").json()
    repository_id = default["repository"]["id"]
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("notes.txt", b"Abstract\nfirst version\n", "text/plain")},
    )
    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    document_id = upload_payload["document"]["id"]
    first_version_id = upload_payload["version"]["id"]

    settings = default["settings"]
    settings["chunking"]["chunk_size"] = 400
    settings_response = client.put(
        f"/repositories/{repository_id}/settings",
        json={"settings": settings},
    )
    documents_before = client.get(f"/repositories/{repository_id}/documents")
    reprocess_response = client.post(
        f"/repositories/{repository_id}/documents/{document_id}/reprocess"
    )
    current_payload = reprocess_response.json()
    prior_response = client.get(
        f"/repositories/{repository_id}/documents/{document_id}/versions/{first_version_id}"
    )

    assert settings_response.status_code == 200
    assert documents_before.status_code == 200
    assert (
        documents_before.json()[0]["current_version"]["metadata"]["reprocess_status"]["status"]
        == "stale"
    )
    assert reprocess_response.status_code == 200
    assert current_payload["version"]["id"] != first_version_id
    assert current_payload["document"]["current_version_id"] == current_payload["version"]["id"]
    assert (
        current_payload["version"]["metadata"]["reprocess"]["source_version_id"] == first_version_id
    )
    assert current_payload["version"]["metadata"]["reprocess"]["changed_fields"] == [
        "chunking.chunk_size"
    ]
    assert current_payload["version"]["metadata"]["reprocess_status"]["status"] == "current"
    assert prior_response.status_code == 200
    assert prior_response.json()["version"]["id"] == first_version_id
    assert prior_response.json()["chunks"][0]["text"] == "Abstract\nfirst version"


def test_delete_all_repository_documents() -> None:
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    first_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("first.txt", b"first document\n", "text/plain")},
    )
    second_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("second.txt", b"second document\n", "text/plain")},
    )

    delete_response = client.delete(f"/repositories/{repository_id}/documents")
    documents_response = client.get(f"/repositories/{repository_id}/documents")
    first_inspection = client.get(
        f"/repositories/{repository_id}/documents/{first_response.json()['document']['id']}"
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert delete_response.status_code == 204
    assert documents_response.json() == []
    assert first_inspection.status_code == 404


def test_annotation_upload_links_to_matching_text_file() -> None:
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    text_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("sample.txt", b"precursor was heated\n", "text/plain")},
    )
    annotation_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("sample.ann", b"T1\tMaterial 0 9\tprecursor\n", "text/plain")},
    )

    assert text_response.status_code == 200
    assert annotation_response.status_code == 200
    metadata = annotation_response.json()["version"]["metadata"]
    assert metadata["paired_text_document_id"] == text_response.json()["document"]["id"]
    assert metadata["paired_text_version_id"] == text_response.json()["version"]["id"]
    assert metadata["paired_text_filename"] == "sample.txt"


def test_repository_manifest_includes_uploaded_source_files() -> None:
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("notes.txt", b"hello corpus\n", "text/plain")},
    )

    manifest_response = client.get(f"/repositories/{repository_id}/manifest")

    assert upload_response.status_code == 200
    assert manifest_response.status_code == 200
    assert manifest_response.json()["source_files"] == [
        upload_response.json()["version"]["storage_path"]
    ]


def test_batch_reprocess_selected_and_all_repository_documents() -> None:
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    first_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("first.txt", b"first document\n", "text/plain")},
    )
    second_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("second.txt", b"second document\n", "text/plain")},
    )
    first_id = first_response.json()["document"]["id"]
    second_id = second_response.json()["document"]["id"]

    selected_response = client.post(
        f"/repositories/{repository_id}/documents/batch/reprocess",
        json={"document_ids": [first_id]},
    )
    all_response = client.post(
        f"/repositories/{repository_id}/documents/batch/reprocess",
        json={"document_ids": [], "all_repository_documents": True},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert selected_response.status_code == 200
    assert selected_response.json()["requested_count"] == 1
    assert selected_response.json()["results"][0]["status"] == "completed"
    assert all_response.status_code == 200
    assert all_response.json()["requested_count"] == 2
    assert {result["document_id"] for result in all_response.json()["results"]} == {
        first_id,
        second_id,
    }
    assert {result["status"] for result in all_response.json()["results"]} == {"completed"}


def test_batch_reprocess_reports_empty_missing_source_and_wrong_repository(
    tmp_path: Path,
) -> None:
    client, session_factory = _client_with_database_session_factory()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    missing_source_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("missing-source.txt", b"missing source\n", "text/plain")},
    )
    missing_source_payload = missing_source_response.json()
    Path(missing_source_payload["version"]["storage_path"]).unlink()
    with session_factory() as session:
        other_repository = Repository(name="Other Repository", root_path=str(tmp_path / "other"))
        session.add(other_repository)
        session.flush()
        session.add(
            RepositorySettingsRow(
                repository_id=other_repository.id,
                settings=created["settings"],
            )
        )
        session.commit()
        other_document = upload_document(
            session,
            other_repository.id,
            "other.txt",
            "text/plain",
            b"other repository document\n",
            settings=Settings(data_dir=tmp_path),
        )
        assert other_document is not None
        other_document_id = other_document.document.id

    empty_response = client.post(
        f"/repositories/{repository_id}/documents/batch/reprocess",
        json={"document_ids": []},
    )
    mixed_response = client.post(
        f"/repositories/{repository_id}/documents/batch/reprocess",
        json={
            "document_ids": [
                missing_source_payload["document"]["id"],
                other_document_id,
                "missing",
            ]
        },
    )

    assert missing_source_response.status_code == 200
    assert empty_response.status_code == 200
    assert empty_response.json()["results"] == []
    assert mixed_response.status_code == 200
    assert [result["status"] for result in mixed_response.json()["results"]] == [
        "missing_source",
        "failed",
        "failed",
    ]
    assert mixed_response.json()["results"][1]["error"] == "Document not found in repository."


def test_batch_ocr_reports_ineligible_missing_dependency_and_completed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRIVATE_RAG_DATA_DIR", str(tmp_path))
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    text_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("notes.txt", b"text is not OCR eligible\n", "text/plain")},
    )
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
        ingestion_service, "render_pages_for_ocr", lambda **kwargs: ([fake_image], [])
    )
    pdf_missing_dependency_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("missing-provider.pdf", b"%PDF scan", "application/pdf")},
    )
    monkeypatch.setattr(
        ingestion_service,
        "resolve_default_ocr_provider",
        lambda *args, **kwargs: (
            None,
            OcrProviderUnavailable(
                provider_name="ocrmypdf_tesseract",
                dependency_name="tesseract",
                message="Tesseract CLI is not installed or is not on PATH.",
            ),
        ),
    )
    mixed_response = client.post(
        f"/repositories/{repository_id}/documents/batch/ocr",
        json={
            "document_ids": [
                text_response.json()["document"]["id"],
                pdf_missing_dependency_response.json()["document"]["id"],
            ]
        },
    )
    monkeypatch.setattr(
        ingestion_service,
        "resolve_default_ocr_provider",
        lambda *args, **kwargs: (FakeOcrProvider(), None),
    )
    pdf_completed_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("completed.pdf", b"%PDF scan again", "application/pdf")},
    )
    completed_response = client.post(
        f"/repositories/{repository_id}/documents/batch/ocr",
        json={"document_ids": [pdf_completed_response.json()["document"]["id"]]},
    )

    assert text_response.status_code == 200
    assert pdf_missing_dependency_response.status_code == 200
    assert mixed_response.status_code == 200
    assert [result["status"] for result in mixed_response.json()["results"]] == [
        "ineligible",
        "missing_dependency",
    ]
    assert completed_response.status_code == 200
    assert completed_response.json()["results"][0]["status"] == "completed"
    assert completed_response.json()["results"][0]["version"]["metadata"]["ocr_run"]["status"] == (
        "completed"
    )


def test_batch_delete_deletes_only_selected_documents() -> None:
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    selected_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("selected.txt", b"selected document\n", "text/plain")},
    )
    preserved_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("preserved.txt", b"preserved document\n", "text/plain")},
    )
    selected_id = selected_response.json()["document"]["id"]
    preserved_id = preserved_response.json()["document"]["id"]

    delete_response = client.post(
        f"/repositories/{repository_id}/documents/batch/delete",
        json={"document_ids": [selected_id, "missing"]},
    )
    documents_response = client.get(f"/repositories/{repository_id}/documents")

    assert selected_response.status_code == 200
    assert preserved_response.status_code == 200
    assert delete_response.status_code == 200
    assert [result["status"] for result in delete_response.json()["results"]] == [
        "deleted",
        "failed",
    ]
    assert client.get(f"/repositories/{repository_id}/documents/{selected_id}").status_code == 404
    assert [document["id"] for document in documents_response.json()] == [preserved_id]
