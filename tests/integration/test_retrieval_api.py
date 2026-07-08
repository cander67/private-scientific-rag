from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.api.app import create_app
from private_rag.api.routes.repositories import get_db_session
from private_rag.api.routes.retrieval import get_reranker_provider
from private_rag.api.routes.vector import get_embedding_provider, get_vector_store
from private_rag.db.base import Base
from private_rag.retrieval.models import RetrievalRun
from private_rag.retrieval.schemas import RetrievalSearchResult
from private_rag.retrieval.service import MAX_RETRIEVAL_HISTORIES_PER_REPOSITORY
from private_rag.vector.embeddings import DeterministicEmbeddingProvider
from private_rag.vector.store import InMemoryVectorStore


class _FakeReranker:
    def score(
        self,
        query: str,
        results: list[RetrievalSearchResult],
        model_name: str,
    ) -> list[float]:
        return [
            1.0 if "adhesion" in (result.text_preview or result.snippet or "") else 0.1
            for result in results
        ]


def _client_with_retrieval_fakes() -> tuple[TestClient, sessionmaker[Session]]:
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
    app.dependency_overrides[get_reranker_provider] = lambda: _FakeReranker()
    return TestClient(app), session_factory


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


def test_retrieval_full_text_mode_persists_run_and_score_breakdown() -> None:
    client, session_factory = _client_with_retrieval_fakes()
    repository_id = _default_repository_id(client)
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "rare-materials.txt",
                b"Abstract\nLiFePO4 conductivity improves after UV-Vis inspection.\n",
                "text/plain",
            )
        },
    )
    rebuild_response = client.post(f"/repositories/{repository_id}/full-text/rebuild")

    response = client.post(
        f"/repositories/{repository_id}/retrieval/search",
        json={"query": "LiFePO4", "mode": "full_text", "top_k": 5},
    )

    assert upload_response.status_code == 200
    assert rebuild_response.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "full_text"
    assert payload["candidate_pool_size"] == 25
    assert payload["rrf_constant"] == 60
    result = payload["results"][0]
    assert result["chunk_id"] == upload_response.json()["chunks_preview"][0]["id"]
    assert result["source_ranks"] == {"full_text": 1, "vector": None}
    assert "bm25" in result["score_breakdown"]
    assert "LiFePO4" in result["snippet"]

    with session_factory() as session:
        run = session.get(RetrievalRun, payload["run_id"])
        assert run is not None
        assert run.mode == "full_text"
        assert run.top_k == 5
        assert run.candidate_pool_size == 25
        assert len(run.results) == 1
        assert run.results[0].chunk_id == result["chunk_id"]


def test_retrieval_vector_mode_returns_embedding_metadata() -> None:
    client, _ = _client_with_retrieval_fakes()
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

    response = client.post(
        f"/repositories/{repository_id}/retrieval/search",
        json={
            "query": "lithium phosphate battery",
            "mode": "vector",
            "top_k": 5,
            "candidate_pool_size": 12,
        },
    )

    assert upload_response.status_code == 200
    assert rebuild_response.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "vector"
    assert payload["candidate_pool_size"] == 12
    result = payload["results"][0]
    assert result["source_ranks"] == {"full_text": None, "vector": 1}
    assert "dense" in result["score_breakdown"]
    assert result["embedding_model"] == "test-deterministic"
    assert result["embedding_run_id"] == rebuild_response.json()["embedding_run_id"]
    assert result["collection_name"].endswith("_latest")


def test_retrieval_hybrid_mode_merges_full_text_and_vector_scores() -> None:
    client, session_factory = _client_with_retrieval_fakes()
    repository_id = _default_repository_id(client)
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "hybrid-materials.txt",
                (
                    b"Abstract\n"
                    b"Lithium iron phosphate cathodes retain capacity during cycling.\n"
                    b"Methods\n"
                    b"LiFePO4 binders improve electrode adhesion.\n"
                ),
                "text/plain",
            )
        },
    )
    full_text_rebuild = client.post(f"/repositories/{repository_id}/full-text/rebuild")
    vector_rebuild = client.post(f"/repositories/{repository_id}/vector/rebuild")

    response = client.post(
        f"/repositories/{repository_id}/retrieval/search",
        json={
            "query": "LiFePO4",
            "mode": "hybrid",
            "top_k": 5,
            "rrf_constant": 30,
        },
    )

    assert upload_response.status_code == 200
    assert full_text_rebuild.status_code == 200
    assert vector_rebuild.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "hybrid"
    assert payload["rrf_constant"] == 30
    result = payload["results"][0]
    assert result["chunk_id"] == upload_response.json()["chunks_preview"][0]["id"]
    assert result["source_ranks"]["full_text"] == 1
    assert result["source_ranks"]["vector"] == 1
    assert result["score_breakdown"]["bm25"] is not None
    assert result["score_breakdown"]["dense"] is not None
    assert result["score_breakdown"]["rrf"] > 0

    with session_factory() as session:
        run = session.get(RetrievalRun, payload["run_id"])
        assert run is not None
        assert run.mode == "hybrid"
        assert run.rrf_constant == 30
        assert run.results[0].score_breakdown["rrf"] == result["score_breakdown"]["rrf"]


def test_retrieval_hybrid_mode_requires_rebuilt_vector_index() -> None:
    client, _ = _client_with_retrieval_fakes()
    repository_id = _default_repository_id(client)
    client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "hybrid-missing-vector.txt",
                b"Abstract\nLiFePO4 conductivity improves after UV-Vis inspection.\n",
                "text/plain",
            )
        },
    )
    client.post(f"/repositories/{repository_id}/full-text/rebuild")

    response = client.post(
        f"/repositories/{repository_id}/retrieval/search",
        json={"query": "LiFePO4", "mode": "hybrid", "top_k": 5},
    )

    assert response.status_code == 409
    assert "Vector index has not been rebuilt" in response.json()["detail"]


def test_retrieval_cross_encoder_reranking_persists_rerank_score() -> None:
    client, session_factory = _client_with_retrieval_fakes()
    repository_id = _default_repository_id(client)
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "rerank-materials.txt",
                (
                    b"Abstract\n"
                    b"Lithium iron phosphate cathodes retain capacity during cycling.\n"
                    b"Methods\n"
                    b"LiFePO4 electrode adhesion improves with polymer binders.\n"
                ),
                "text/plain",
            )
        },
    )
    client.post(f"/repositories/{repository_id}/full-text/rebuild")
    client.post(f"/repositories/{repository_id}/vector/rebuild")

    response = client.post(
        f"/repositories/{repository_id}/retrieval/search",
        json={
            "query": "LiFePO4 adhesion",
            "mode": "hybrid",
            "top_k": 5,
            "reranker_strategy": "cross_encoder",
        },
    )

    assert upload_response.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    result = payload["results"][0]
    assert payload["reranker_strategy"] == "cross_encoder"
    assert result["score_breakdown"]["rerank"] == 1.0
    assert result["final_score"] == 1.0

    with session_factory() as session:
        run = session.get(RetrievalRun, payload["run_id"])
        assert run is not None
        assert run.reranker_strategy == "cross_encoder"
        assert run.reranker_model == "cross-encoder/ms-marco-MiniLM-L6-v2"
        assert run.results[0].score_breakdown["rerank"] == 1.0


def test_retrieval_metadata_boost_reranking_reports_boost() -> None:
    client, _ = _client_with_retrieval_fakes()
    repository_id = _default_repository_id(client)
    upload_response = client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "metadata-boost.txt",
                b"Abstract\nLiFePO4 conductivity improves after UV-Vis inspection.\n",
                "text/plain",
            )
        },
    )
    client.post(f"/repositories/{repository_id}/full-text/rebuild")

    response = client.post(
        f"/repositories/{repository_id}/retrieval/search",
        json={
            "query": "LiFePO4",
            "mode": "full_text",
            "top_k": 5,
            "reranker_strategy": "metadata_boost",
            "metadata_boosts": {
                "section": "high",
                "patent_section": "low",
                "document_kind": "low",
                "table_figure": "low",
            },
        },
    )

    assert upload_response.status_code == 200
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["score_breakdown"]["metadata_boost"] == 0.3
    assert result["final_score"] > abs(result["score_breakdown"]["bm25"])


def test_retrieval_rejects_future_only_reranker_strategy() -> None:
    client, _ = _client_with_retrieval_fakes()
    repository_id = _default_repository_id(client)

    response = client.post(
        f"/repositories/{repository_id}/retrieval/search",
        json={
            "query": "LiFePO4",
            "mode": "full_text",
            "reranker_strategy": "diversity_mmr",
        },
    )

    assert response.status_code == 422


def test_retrieval_history_keeps_five_recent_runs_per_repository() -> None:
    client, session_factory = _client_with_retrieval_fakes()
    repository_id = _default_repository_id(client)
    client.post(
        f"/repositories/{repository_id}/documents",
        files={
            "file": (
                "history-materials.txt",
                b"Abstract\nLiFePO4 conductivity improves after UV-Vis inspection.\n",
                "text/plain",
            )
        },
    )
    client.post(f"/repositories/{repository_id}/full-text/rebuild")

    run_ids = []
    for index in range(MAX_RETRIEVAL_HISTORIES_PER_REPOSITORY + 1):
        response = client.post(
            f"/repositories/{repository_id}/retrieval/search",
            json={"query": f"LiFePO4 {index}", "mode": "full_text", "top_k": 5},
        )
        assert response.status_code == 200
        run_ids.append(response.json()["run_id"])

    with session_factory() as session:
        retained = list(
            session.scalars(
                select(RetrievalRun)
                .where(RetrievalRun.repository_id == repository_id)
                .order_by(RetrievalRun.created_at.desc(), RetrievalRun.id.desc())
            )
        )
        assert len(retained) == MAX_RETRIEVAL_HISTORIES_PER_REPOSITORY
        assert run_ids[0] not in {run.id for run in retained}
