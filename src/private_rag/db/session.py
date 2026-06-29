from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from private_rag.core.settings import Settings, get_settings


def create_db_engine(settings: Settings | None = None) -> Engine:
    resolved = settings or get_settings()
    ensure_sqlite_parent(resolved.database_url)
    connect_args = (
        {"check_same_thread": False} if resolved.database_url.startswith("sqlite") else {}
    )
    return create_engine(resolved.database_url, connect_args=connect_args)


def ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return

    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path == ":memory:":
        return

    Path(raw_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
