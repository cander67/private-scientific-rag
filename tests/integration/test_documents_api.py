from __future__ import annotations

from collections.abc import Generator

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
    assert payload["chunks_preview"][0]["line_start"] == 1
    assert payload["chunks_preview"][0]["metadata"]["source_type"] == "text"


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
