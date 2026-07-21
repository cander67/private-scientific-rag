from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

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


def test_rebuild_and_search_full_text_index_returns_citation_ready_results() -> None:
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "rare-materials.txt",
                (
                    b"Abstract\nLiFePO4 conductivity improves after UV-Vis inspection.\n"
                    b"Claims\nThe cathode blend includes epoxy acrylate binder.\n"
                ),
                "text/plain",
            )
        },
    )

    rebuild_response = client.post(f"/repositories/{repository_id}/full-text/rebuild")
    search_response = client.post(
        f"/repositories/{repository_id}/full-text/search",
        json={"query": "LiFePO4", "limit": 5},
    )
    filtered_response = client.post(
        f"/repositories/{repository_id}/full-text/search",
        json={
            "query": "epoxy acrylate",
            "filters": {"document_id": upload_response.json()["document"]["id"]},
        },
    )

    assert upload_response.status_code == 200
    assert rebuild_response.status_code == 200
    assert rebuild_response.json()["indexed_chunks"] >= 1
    assert search_response.status_code == 200
    result = search_response.json()["results"][0]
    assert result["rank"] == 1
    assert isinstance(result["score"], float)
    assert result["document_id"] == upload_response.json()["document"]["id"]
    assert result["chunk_id"] == upload_response.json()["chunks_preview"][0]["id"]
    assert result["line_start"] == 1
    assert "LiFePO4" in result["snippet"]
    assert "body" in result["matched_fields"]
    assert filtered_response.status_code == 200
    assert filtered_response.json()["results"][0]["document_title"] == "rare-materials.txt"


def test_full_text_search_filters_by_available_metadata() -> None:
    client = _client_with_database()
    repository_id = client.get("/repositories/default").json()["repository"]["id"]
    pdf_bytes = (
        b"%PDF-1.4\n/Type /Page\n"
        b"Title: UV Curable Epoxy Acrylate Adhesive Composition\n"
        b"Abstract\nFigure 1 shows the adhesive test layout.\n"
        b"Table 2 reports UV-Vis absorbance for LiFePO4 samples.\n"
        b"What is claimed is:\n1. A composition comprising epoxy acrylate resin.\n%%EOF"
    )
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("US11370944.pdf", pdf_bytes, "application/pdf")},
    )

    rebuild_response = client.post(f"/repositories/{repository_id}/full-text/rebuild")
    filtered_response = client.post(
        f"/repositories/{repository_id}/full-text/search",
        json={
            "query": "epoxy acrylate",
            "filters": {
                "document_kind": "patent_pdf",
                "has_table": True,
                "has_figure": True,
                "patent_section": "claims",
            },
        },
    )

    assert upload_response.status_code == 200
    assert rebuild_response.status_code == 200
    assert filtered_response.status_code == 200
    result = filtered_response.json()["results"][0]
    assert result["document_title"] == "US11370944.pdf"
    assert result["metadata"]["document_kind"] == "patent_pdf"
    assert result["metadata"]["has_table"] is True
    assert result["metadata"]["has_figure"] is True
    assert "claims" in result["metadata"]["patent_sections"]


def test_full_text_rebuild_blocks_stale_parser_chunks_then_indexes_current_version() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={"file": ("refresh.txt", b"Abstract\nfirst only marker\n", "text/plain")},
    )
    assert upload_response.status_code == 200
    source_path = Path(upload_response.json()["version"]["storage_path"])
    source_path.write_bytes(b"Abstract\nsecond only marker\n")
    settings = created["settings"]
    settings["chunking"]["chunk_size"] = 400
    settings_response = client.put(
        f"/repositories/{repository_id}/settings",
        json={"settings": settings},
    )

    stale_rebuild = client.post(f"/repositories/{repository_id}/full-text/rebuild")
    reprocess_response = client.post(
        f"/repositories/{repository_id}/documents/{upload_response.json()['document']['id']}/reprocess"
    )
    clean_rebuild = client.post(f"/repositories/{repository_id}/full-text/rebuild")
    old_search = client.post(
        f"/repositories/{repository_id}/full-text/search",
        json={"query": "first only marker"},
    )
    new_search = client.post(
        f"/repositories/{repository_id}/full-text/search",
        json={"query": "second only marker"},
    )

    assert settings_response.status_code == 200
    assert stale_rebuild.status_code == 409
    assert "Reprocess stale documents before rebuilding indexes" in stale_rebuild.json()["detail"]
    assert reprocess_response.status_code == 200
    assert clean_rebuild.status_code == 200
    assert (
        clean_rebuild.json()["indexed_chunks"]
        == reprocess_response.json()["version"]["chunk_count"]
    )
    assert old_search.status_code == 200
    assert old_search.json()["results"] == []
    assert new_search.status_code == 200
    assert (
        new_search.json()["results"][0]["document_version_id"]
        == reprocess_response.json()["version"]["id"]
    )


def test_full_text_search_returns_404_for_missing_repository() -> None:
    client = _client_with_database()

    response = client.post(
        "/repositories/missing/full-text/search",
        json={"query": "LiFePO4"},
    )

    assert response.status_code == 404
