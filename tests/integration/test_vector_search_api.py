from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.api.app import create_app
from private_rag.api.routes.repositories import get_db_session
from private_rag.api.routes.vector import get_embedding_provider, get_vector_store
from private_rag.db.base import Base
from private_rag.vector.embeddings import DeterministicEmbeddingProvider
from private_rag.vector.store import InMemoryVectorStore


def _client_with_vector_fakes() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    store = InMemoryVectorStore()
    embedder = DeterministicEmbeddingProvider(vector_size=8)

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedding_provider] = lambda: embedder
    return TestClient(app)


def _default_repository_id(client: TestClient) -> str:
    response = client.get("/repositories/default")
    payload = response.json()
    settings = payload["settings"]
    settings["embedding"]["model"] = "test-deterministic"
    settings["vector"]["vector_size"] = 8
    update_response = client.put(
        f"/repositories/{payload['repository']['id']}/settings",
        json={"settings": settings},
    )
    assert update_response.status_code == 200
    return str(payload["repository"]["id"])


def test_rebuild_and_search_vector_index_returns_embedding_metadata() -> None:
    client = _client_with_vector_fakes()
    repository_id = _default_repository_id(client)
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "semantic-materials.txt",
                (
                    b"Abstract\n"
                    b"Lithium iron phosphate cathodes retain capacity during cycling.\n"
                    b"Methods\n"
                    b"UV curable epoxy acrylate binders improve adhesive strength.\n"
                ),
                "text/plain",
            )
        },
    )

    rebuild_response = client.post(f"/repositories/{repository_id}/vector/rebuild")
    search_response = client.post(
        f"/repositories/{repository_id}/vector/search",
        json={"query": "lithium phosphate battery", "limit": 5},
    )

    assert upload_response.status_code == 200
    assert rebuild_response.status_code == 200
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["indexed_chunks"] >= 1
    assert rebuild_payload["model"] == "test-deterministic"
    assert rebuild_payload["vector_size"] == 8
    assert rebuild_payload["collection_name"].endswith("_latest")

    assert search_response.status_code == 200
    payload = search_response.json()
    assert payload["embedding_run_id"] == rebuild_payload["embedding_run_id"]
    assert payload["model"] == "test-deterministic"
    result = payload["results"][0]
    assert result["rank"] == 1
    assert isinstance(result["score"], float)
    assert result["distance"] == "cosine"
    assert result["document_id"] == upload_response.json()["document"]["id"]
    assert result["chunk_id"] == upload_response.json()["chunks_preview"][0]["id"]
    assert "Lithium iron phosphate" in result["text_preview"]
    assert result["embedding_run_id"] == rebuild_payload["embedding_run_id"]
    assert result["embedding_model"] == "test-deterministic"


def test_vector_search_filters_match_full_text_filter_surface() -> None:
    client = _client_with_vector_fakes()
    repository_id = _default_repository_id(client)
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

    rebuild_response = client.post(f"/repositories/{repository_id}/vector/rebuild")
    filtered_response = client.post(
        f"/repositories/{repository_id}/vector/search",
        json={
            "query": "adhesive composition",
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


def test_vector_search_requires_rebuilt_index() -> None:
    client = _client_with_vector_fakes()
    repository_id = _default_repository_id(client)

    response = client.post(
        f"/repositories/{repository_id}/vector/search",
        json={"query": "LiFePO4"},
    )

    assert response.status_code == 409
    assert "Vector index has not been rebuilt" in response.json()["detail"]


def test_vector_search_returns_404_for_missing_repository() -> None:
    client = _client_with_vector_fakes()

    response = client.post(
        "/repositories/missing/vector/search",
        json={"query": "LiFePO4"},
    )

    assert response.status_code == 404
