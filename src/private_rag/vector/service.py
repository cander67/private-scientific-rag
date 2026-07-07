from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from private_rag.ingestion.models import Document, DocumentChunk, DocumentVersion
from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import RepositorySettings
from private_rag.search.service import _fields_for_chunk, _split_tags
from private_rag.vector.embeddings import EmbeddingProvider
from private_rag.vector.models import EmbeddingRun
from private_rag.vector.schemas import (
    VectorRebuildResponse,
    VectorSearchFilters,
    VectorSearchResponse,
    VectorSearchResult,
)
from private_rag.vector.store import VectorPoint, VectorStore


class VectorIndexMissingError(RuntimeError):
    pass


def rebuild_vector_index(
    session: Session,
    repository_id: str,
    store: VectorStore,
    embedder: EmbeddingProvider,
) -> VectorRebuildResponse | None:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    settings = RepositorySettings.model_validate(repository.settings.settings)
    collection_name = collection_name_for_repository(repository_id)
    vector_size = embedder.vector_size
    if settings.vector.vector_size != vector_size:
        raise RuntimeError(
            "Embedding model vector size does not match repository vector settings: "
            f"{vector_size} != {settings.vector.vector_size}."
        )

    chunks = session.execute(
        select(DocumentChunk, Document, DocumentVersion)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
        .where(DocumentChunk.repository_id == repository_id)
        .order_by(Document.display_name, DocumentChunk.chunk_index)
    ).all()

    store.recreate_collection(collection_name, vector_size, settings.vector.distance)
    vectors = embedder.embed([chunk.text for chunk, _, _ in chunks]) if chunks else []
    points = [
        VectorPoint(
            id=chunk.id,
            vector=vector,
            payload=_payload_for_chunk(chunk, document, version),
        )
        for (chunk, document, version), vector in zip(chunks, vectors, strict=True)
    ]
    store.upsert_points(collection_name, points)

    embedding_run = session.scalar(
        select(EmbeddingRun).where(EmbeddingRun.repository_id == repository_id)
    )
    settings_snapshot = settings.model_dump(mode="json")
    if embedding_run is None:
        embedding_run = EmbeddingRun(repository_id=repository_id)
    embedding_run.provider = settings.embedding.provider
    embedding_run.model = embedder.model_name
    embedding_run.vector_size = vector_size
    embedding_run.distance = settings.vector.distance
    embedding_run.collection_name = collection_name
    embedding_run.status = "indexed"
    embedding_run.chunk_count = len(points)
    embedding_run.settings_snapshot = settings_snapshot
    embedding_run.is_latest = True
    session.add(embedding_run)
    session.commit()
    session.refresh(embedding_run)

    return VectorRebuildResponse(
        repository_id=repository_id,
        embedding_run_id=embedding_run.id,
        provider=settings.embedding.provider,
        model=embedder.model_name,
        collection_name=collection_name,
        indexed_chunks=len(points),
        vector_size=vector_size,
        distance=settings.vector.distance,
    )


def search_vector_index(
    session: Session,
    repository_id: str,
    query: str,
    limit: int,
    filters: VectorSearchFilters,
    store: VectorStore,
    embedder: EmbeddingProvider,
) -> VectorSearchResponse | None:
    repository = session.get(Repository, repository_id)
    if repository is None:
        return None
    embedding_run = session.scalar(
        select(EmbeddingRun).where(EmbeddingRun.repository_id == repository_id)
    )
    if embedding_run is None or embedding_run.status != "indexed":
        raise VectorIndexMissingError("Vector index has not been rebuilt for this repository.")

    query_vector = embedder.embed([query])[0]
    hits = store.search(
        embedding_run.collection_name,
        query_vector,
        limit,
        filters,
    )
    results = [
        _result_from_hit(rank, hit.payload, hit.score, embedding_run)
        for rank, hit in enumerate(hits, start=1)
    ]
    return VectorSearchResponse(
        query=query,
        repository_id=repository_id,
        embedding_run_id=embedding_run.id,
        provider=embedding_run.provider,
        model=embedding_run.model,
        collection_name=embedding_run.collection_name,
        vector_size=embedding_run.vector_size,
        distance=embedding_run.distance,
        results=results,
    )


def collection_name_for_repository(repository_id: str) -> str:
    normalized = repository_id.replace("-", "_")
    return f"repository_{normalized}_latest"


def _payload_for_chunk(
    chunk: DocumentChunk,
    document: Document,
    version: DocumentVersion,
) -> dict[str, Any]:
    fields = _fields_for_chunk(chunk, document, version)
    tags = _split_tags(fields["tags"])
    patent_sections = _split_tags(fields["patent_sections"])
    return {
        "repository_id": fields["repository_id"],
        "document_id": fields["document_id"],
        "document_version_id": fields["document_version_id"],
        "chunk_id": fields["chunk_id"],
        "chunk_index": fields["chunk_index"],
        "document_title": fields["document_title"],
        "section": fields["section"],
        "source_type": fields["source_type"],
        "document_kind": fields["document_kind"],
        "tags": tags,
        "has_table": fields["has_table"] == "1",
        "has_figure": fields["has_figure"] == "1",
        "patent_sections": patent_sections,
        "page_start": fields["page_start"],
        "page_end": fields["page_end"],
        "line_start": fields["line_start"],
        "line_end": fields["line_end"],
        "text": chunk.text,
    }


def _result_from_hit(
    rank: int,
    payload: dict[str, Any],
    score: float,
    embedding_run: EmbeddingRun,
) -> VectorSearchResult:
    text = str(payload.get("text") or "")
    return VectorSearchResult(
        rank=rank,
        score=score,
        distance=embedding_run.distance,  # type: ignore[arg-type]
        repository_id=str(payload["repository_id"]),
        document_id=str(payload["document_id"]),
        document_version_id=str(payload["document_version_id"]),
        chunk_id=str(payload["chunk_id"]),
        chunk_index=int(payload["chunk_index"]),
        document_title=str(payload["document_title"]),
        section=payload.get("section"),
        page_start=payload.get("page_start"),
        page_end=payload.get("page_end"),
        line_start=payload.get("line_start"),
        line_end=payload.get("line_end"),
        text_preview=text[:280],
        metadata={
            "source_type": payload.get("source_type"),
            "document_kind": payload.get("document_kind"),
            "tags": payload.get("tags") or [],
            "has_table": payload.get("has_table") is True,
            "has_figure": payload.get("has_figure") is True,
            "patent_sections": payload.get("patent_sections") or [],
        },
        embedding_run_id=embedding_run.id,
        embedding_provider=embedding_run.provider,
        embedding_model=embedding_run.model,
        vector_size=embedding_run.vector_size,
        collection_name=embedding_run.collection_name,
    )
