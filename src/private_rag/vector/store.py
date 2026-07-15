from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from private_rag.vector.schemas import VectorSearchFilters


class VectorStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class VectorPoint:
    id: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass(frozen=True)
class VectorSearchHit:
    id: str
    score: float
    payload: dict[str, Any]


class VectorStore(Protocol):
    def recreate_collection(
        self, collection_name: str, vector_size: int, distance: str
    ) -> None: ...

    def delete_collection(self, collection_name: str) -> None: ...

    def upsert_points(self, collection_name: str, points: list[VectorPoint]) -> None: ...

    def search(
        self,
        collection_name: str,
        vector: list[float],
        limit: int,
        filters: VectorSearchFilters,
    ) -> list[VectorSearchHit]: ...


class QdrantVectorStore:
    def __init__(self, qdrant_url: str) -> None:
        self._base_url = qdrant_url.rstrip("/")

    def recreate_collection(self, collection_name: str, vector_size: int, distance: str) -> None:
        self._request("DELETE", f"/collections/{collection_name}", tolerate_not_found=True)
        self._request(
            "PUT",
            f"/collections/{collection_name}",
            json={
                "vectors": {
                    "size": vector_size,
                    "distance": _qdrant_distance(distance),
                }
            },
        )

    def delete_collection(self, collection_name: str) -> None:
        self._request("DELETE", f"/collections/{collection_name}", tolerate_not_found=True)

    def upsert_points(self, collection_name: str, points: list[VectorPoint]) -> None:
        if not points:
            return
        self._request(
            "PUT",
            f"/collections/{collection_name}/points",
            params={"wait": "true"},
            json={
                "points": [
                    {
                        "id": point.id,
                        "vector": point.vector,
                        "payload": point.payload,
                    }
                    for point in points
                ]
            },
        )

    def search(
        self,
        collection_name: str,
        vector: list[float],
        limit: int,
        filters: VectorSearchFilters,
    ) -> list[VectorSearchHit]:
        body: dict[str, Any] = {
            "vector": vector,
            "limit": limit,
            "with_payload": True,
        }
        qdrant_filter = _qdrant_filter(filters)
        if qdrant_filter:
            body["filter"] = qdrant_filter
        response = self._request(
            "POST",
            f"/collections/{collection_name}/points/search",
            json=body,
        )
        result = response.json().get("result", [])
        return [
            VectorSearchHit(
                id=str(hit["id"]),
                score=float(hit["score"]),
                payload=dict(hit.get("payload") or {}),
            )
            for hit in result
        ]

    def _request(
        self,
        method: str,
        path: str,
        *,
        tolerate_not_found: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.request(method, f"{self._base_url}{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise VectorStoreError(
                f"Qdrant is unavailable at {self._base_url}. Start it with docker compose."
            ) from exc
        if tolerate_not_found and response.status_code == 404:
            return response
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise VectorStoreError(
                f"Qdrant request failed for {path}: HTTP {response.status_code}"
            ) from exc
        return response


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.collections: dict[str, tuple[int, str, list[VectorPoint]]] = {}

    def recreate_collection(self, collection_name: str, vector_size: int, distance: str) -> None:
        self.collections[collection_name] = (vector_size, distance, [])

    def delete_collection(self, collection_name: str) -> None:
        self.collections.pop(collection_name, None)

    def upsert_points(self, collection_name: str, points: list[VectorPoint]) -> None:
        vector_size, distance, existing = self.collections[collection_name]
        by_id = {point.id: point for point in existing}
        by_id.update({point.id: point for point in points})
        self.collections[collection_name] = (vector_size, distance, list(by_id.values()))

    def search(
        self,
        collection_name: str,
        vector: list[float],
        limit: int,
        filters: VectorSearchFilters,
    ) -> list[VectorSearchHit]:
        _, _, points = self.collections.get(collection_name, (0, "cosine", []))
        hits = [
            VectorSearchHit(
                id=point.id,
                score=_dot_product(vector, point.vector),
                payload=point.payload,
            )
            for point in points
            if _matches_filters(point.payload, filters)
        ]
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]


def _qdrant_distance(distance: str) -> str:
    return {
        "cosine": "Cosine",
        "dot": "Dot",
        "euclid": "Euclid",
    }[distance]


def _qdrant_filter(filters: VectorSearchFilters) -> dict[str, Any] | None:
    conditions: list[dict[str, Any]] = []
    _append_match(conditions, "document_id", filters.document_id)
    _append_match(conditions, "section", filters.section)
    _append_match(conditions, "source_type", filters.source_type)
    _append_match(conditions, "document_kind", filters.document_kind)
    _append_match(conditions, "has_table", filters.has_table)
    _append_match(conditions, "has_figure", filters.has_figure)
    _append_match(conditions, "tags", filters.tag)
    _append_match(conditions, "patent_sections", filters.patent_section)
    return {"must": conditions} if conditions else None


def _append_match(conditions: list[dict[str, Any]], key: str, value: Any) -> None:
    if value is not None:
        conditions.append({"key": key, "match": {"value": value}})


def _matches_filters(payload: dict[str, Any], filters: VectorSearchFilters) -> bool:
    checks = {
        "document_id": filters.document_id,
        "section": filters.section,
        "source_type": filters.source_type,
        "document_kind": filters.document_kind,
        "has_table": filters.has_table,
        "has_figure": filters.has_figure,
    }
    for key, value in checks.items():
        if value is not None and payload.get(key) != value:
            return False
    if filters.tag and filters.tag not in payload.get("tags", []):
        return False
    if filters.patent_section and filters.patent_section not in payload.get("patent_sections", []):
        return False
    return True


def _dot_product(left: list[float], right: list[float]) -> float:
    return sum(
        left_value * right_value for left_value, right_value in zip(left, right, strict=False)
    )
