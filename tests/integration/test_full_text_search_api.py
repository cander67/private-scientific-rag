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


def test_full_text_search_returns_404_for_missing_repository() -> None:
    client = _client_with_database()

    response = client.post(
        "/repositories/missing/full-text/search",
        json={"query": "LiFePO4"},
    )

    assert response.status_code == 404
