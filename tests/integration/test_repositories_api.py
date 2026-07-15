from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.api.app import create_app
from private_rag.api.routes.repositories import get_db_session
from private_rag.db.base import Base
from private_rag.repositories import models as repository_models  # noqa: F401
from private_rag.repositories.models import Repository, RepositorySnapshot


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
    app.state.test_session_factory = session_factory
    return TestClient(app)


def test_default_repository_is_created_on_first_request() -> None:
    client = _client_with_database()

    response = client.get("/repositories/default")

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository"]["name"] == "Default Repository"
    assert payload["settings"]["chunking"]["chunk_size"] == 800
    assert payload["settings"]["embedding"]["model"]


def test_repository_list_includes_default_repository() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()

    response = client.get("/repositories")

    assert response.status_code == 200
    assert response.json() == [created["repository"]]


def test_repository_settings_round_trip_and_manifest_export() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    settings = created["settings"]
    settings["chunking"]["chunk_size"] = 1200
    settings["chunking"]["chunk_overlap"] = 160
    settings["full_text"]["tokenizer"] = "porter"
    settings["full_text"]["porter_stemming"] = True
    settings["prompt"]["version"] = "science-v2"

    update_response = client.put(
        f"/repositories/{repository_id}/settings",
        json={"settings": settings},
    )
    manifest_response = client.get(f"/repositories/{repository_id}/manifest")

    assert update_response.status_code == 200
    assert update_response.json()["settings"]["prompt"]["version"] == "science-v2"
    assert manifest_response.status_code == 200
    manifest = manifest_response.json()
    assert manifest["settings"]["chunking"]["chunk_size"] == 1200
    assert manifest["settings"]["parser"]["structured_parser"]
    assert manifest["settings"]["full_text"]["tokenizer"] == "porter"
    assert manifest["settings"]["full_text"]["porter_stemming"] is True


def test_repository_settings_save_creates_snapshot_and_stays_scoped() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]

    test_app = cast(Any, client.app)
    with test_app.state.test_session_factory() as session:
        other_repository = Repository(name="Other Repository")
        session.add(other_repository)
        session.flush()
        other_settings = deepcopy(created["settings"])
        other_settings["chunking"] = {
            **created["settings"]["chunking"],
            "chunk_size": 777,
        }
        other_repository.settings = repository_models.RepositorySettingsRow(settings=other_settings)
        session.commit()
        other_repository_id = other_repository.id

    settings = created["settings"]
    settings["chunking"]["chunk_size"] = 1400

    response = client.put(
        f"/repositories/{repository_id}/settings",
        json={"settings": settings},
    )

    assert response.status_code == 200
    assert (
        client.get(f"/repositories/{repository_id}/settings").json()["settings"]["chunking"][
            "chunk_size"
        ]
        == 1400
    )
    assert (
        client.get(f"/repositories/{other_repository_id}/settings").json()["settings"]["chunking"][
            "chunk_size"
        ]
        == 777
    )
    with test_app.state.test_session_factory() as session:
        snapshots = session.query(RepositorySnapshot).filter_by(repository_id=repository_id).all()
        assert len(snapshots) == 1
        assert snapshots[0].manifest["settings"]["chunking"]["chunk_size"] == 1400


def test_repository_settings_endpoint_rejects_invalid_settings() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    settings = created["settings"]
    settings["chunking"]["chunk_overlap"] = settings["chunking"]["chunk_size"]

    response = client.put(
        f"/repositories/{repository_id}/settings",
        json={"settings": settings},
    )

    assert response.status_code == 422
    assert "chunk_overlap must be smaller" in response.text


def test_repository_settings_impact_endpoint_reports_categories() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    settings = created["settings"]
    settings["chunking"]["mode"] = "fixed"
    settings["embedding"]["model"] = "sentence-transformers/other"
    settings["reranking"]["model"] = "cross-encoder/other"
    settings["export"]["include_sources"] = False

    response = client.post(
        f"/repositories/{repository_id}/settings/impact",
        json={"settings": settings},
    )

    assert response.status_code == 200
    payload = response.json()
    categories = {impact["category"] for impact in payload["impacts"]}
    assert payload["has_changes"] is True
    assert "document_reprocessing" in categories
    assert "vector_rebuild" in categories
    assert "retrieval_defaults" in categories
    assert "export_recreate" in categories


def test_recreate_validation_endpoint_reports_clear_issues(tmp_path: Path) -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    manifest = client.get(f"/repositories/{created['repository']['id']}/manifest").json()
    manifest["source_files"] = [str(tmp_path / "missing.pdf")]

    response = client.post(
        "/repositories/recreate/validate",
        json={"manifest": manifest, "available_models": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_recreate"] is False
    assert payload["missing_source_files"][0]["code"] == "missing_source_file"
