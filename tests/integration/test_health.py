from __future__ import annotations

from fastapi.testclient import TestClient

from private_rag.api.app import create_app


def test_health_endpoint_reports_local_status() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["local_only"] is True
    assert payload["app"] == "private-scientific-rag"
    assert "qdrant" in payload
