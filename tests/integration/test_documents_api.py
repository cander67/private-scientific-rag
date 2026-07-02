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
from private_rag.db.base import Base


def _client_with_database() -> TestClient:
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
    return TestClient(app)


def _pdf_bytes_with_text(text: str) -> bytes:
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = BytesIO()
    document.save(data)
    return data.getvalue()


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
