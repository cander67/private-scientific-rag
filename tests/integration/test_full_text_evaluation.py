from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.core.settings import Settings
from private_rag.db.base import Base
from private_rag.ingestion.service import upload_document
from private_rag.repositories.service import ensure_default_repository
from private_rag.search.evaluation import ExactMatchQuery, evaluate_exact_match_recall


def test_prd4_exact_match_recall_fixture_is_ci_gated(tmp_path: Path) -> None:
    fixture = _load_fixture()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    app_settings = Settings(data_dir=tmp_path)

    with session_factory() as session:
        repository = ensure_default_repository(session, app_settings).repository
        for document in fixture["documents"]:
            uploaded = upload_document(
                session=session,
                repository_id=repository.id,
                filename=str(document["filename"]),
                content_type=str(document["content_type"]),
                data=str(document["content"]).encode("utf-8"),
                settings=app_settings,
            )
            assert uploaded is not None

        queries = [ExactMatchQuery.model_validate(item) for item in fixture["queries"]]
        result = evaluate_exact_match_recall(session, repository.id, queries)

    assert result is not None
    assert result.indexed_chunks >= 2
    assert {metric.k: metric.recall for metric in result.metrics} == {5: 1.0, 10: 1.0}


def _load_fixture() -> dict[str, list[dict[str, Any]]]:
    path = Path(__file__).parents[1] / "fixtures" / "search" / "prd4_exact_match_fixture.json"
    return cast(dict[str, list[dict[str, Any]]], json.loads(path.read_text(encoding="utf-8")))
