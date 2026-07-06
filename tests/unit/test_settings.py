from __future__ import annotations

from pathlib import Path

from private_rag.core.settings import Settings
from private_rag.db.session import ensure_sqlite_parent


def test_settings_parse_cors_origins() -> None:
    settings = Settings.model_validate(
        {"CORS_ORIGINS": "http://localhost:5173, http://127.0.0.1:5173"}
    )

    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_sqlite_database_url_is_safe_to_report() -> None:
    settings = Settings(database_url="sqlite:///./data/private_rag.sqlite")

    assert settings.safe_database_url == "sqlite:///./data/private_rag.sqlite"


def test_sqlite_parent_directory_is_created(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "private_rag.sqlite"

    ensure_sqlite_parent(f"sqlite:///{database_path}")

    assert database_path.parent.exists()
