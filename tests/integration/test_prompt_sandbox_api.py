from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.api.app import create_app
from private_rag.api.routes.repositories import get_db_session
from private_rag.db.base import Base
from private_rag.repositories import models as repository_models  # noqa: F401


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


def test_sandbox_prompt_versions_copy_to_and_from_chat_library_without_changing_defaults() -> None:
    client = _client_with_database()
    created = client.get("/repositories/default").json()
    repository_id = created["repository"]["id"]
    original_active_prompt_id = created["settings"]["prompt"]["active_chat_prompt_id"]
    chat_prompt_id = created["settings"]["prompt"]["library"][0]["id"]

    create_response = client.post(
        f"/repositories/{repository_id}/prompt-sandbox/prompts",
        json={
            "name": "Sandbox citation prompt",
            "notes": "Try stricter evidence language.",
            "source_chat_prompt_id": chat_prompt_id,
        },
    )

    assert create_response.status_code == 200
    prompt = create_response.json()
    assert prompt["name"] == "Sandbox citation prompt"
    assert prompt["notes"] == "Try stricter evidence language."
    assert prompt["body"] == created["settings"]["prompt"]["library"][0]["text"]
    assert prompt["source_chat_prompt_id"] == chat_prompt_id
    assert prompt["used_by_run"] is False

    list_response = client.get(f"/repositories/{repository_id}/prompt-sandbox/prompts")
    read_response = client.get(
        f"/repositories/{repository_id}/prompt-sandbox/prompts/{prompt['id']}"
    )

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [prompt["id"]]
    assert read_response.status_code == 200
    assert read_response.json()["body"] == prompt["body"]

    copy_response = client.post(
        f"/repositories/{repository_id}/prompt-sandbox/prompts/{prompt['id']}/copy-to-chat-library",
        json={"name": "Vetted sandbox prompt"},
    )
    settings_response = client.get(f"/repositories/{repository_id}/settings")

    assert copy_response.status_code == 200
    copied = copy_response.json()
    settings = settings_response.json()["settings"]
    assert copied["id"] != original_active_prompt_id
    assert copied["name"] == "Vetted sandbox prompt"
    assert copied["text"] == prompt["body"]
    assert settings["prompt"]["active_chat_prompt_id"] == original_active_prompt_id
    assert any(entry["id"] == copied["id"] for entry in settings["prompt"]["library"])
