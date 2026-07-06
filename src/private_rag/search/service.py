from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from private_rag.ingestion.models import Document, DocumentChunk, DocumentVersion
from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import FullTextSettings, RepositorySettings
from private_rag.search.schemas import (
    FullTextRebuildResponse,
    FullTextSearchFilters,
    FullTextSearchResponse,
    FullTextSearchResult,
)

FTS_TABLE = "full_text_chunks"
REQUIRED_FTS_COLUMNS = {
    "repository_id",
    "document_id",
    "document_version_id",
    "chunk_id",
    "chunk_index",
    "document_title",
    "section",
    "source_type",
    "document_kind",
    "tags",
    "has_table",
    "has_figure",
    "patent_sections",
    "page_start",
    "page_end",
    "line_start",
    "line_end",
    "title",
    "headings",
    "body",
    "captions",
    "tables",
    "claims",
    "examples",
}
FIELD_WEIGHTS = {
    "title": 6.0,
    "headings": 5.0,
    "body": 1.0,
    "captions": 3.0,
    "tables": 2.5,
    "claims": 4.0,
    "examples": 3.5,
}
INDEXED_FIELDS = tuple(FIELD_WEIGHTS)


def field_weight_configuration() -> dict[str, float]:
    return dict(FIELD_WEIGHTS)


def rebuild_full_text_index(
    session: Session,
    repository_id: str,
) -> FullTextRebuildResponse | None:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    full_text_settings = RepositorySettings.model_validate(repository.settings.settings).full_text
    ensure_full_text_schema(session, full_text_settings)
    session.execute(
        text(f"DELETE FROM {FTS_TABLE} WHERE repository_id = :repository_id"),
        {"repository_id": repository_id},
    )

    chunks = session.execute(
        select(DocumentChunk, Document, DocumentVersion)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
        .where(DocumentChunk.repository_id == repository_id)
        .order_by(Document.display_name, DocumentChunk.chunk_index)
    ).all()

    for chunk, document, version in chunks:
        fields = _fields_for_chunk(chunk, document, version)
        session.execute(
            text(
                f"""
                INSERT INTO {FTS_TABLE} (
                    repository_id, document_id, document_version_id, chunk_id, chunk_index,
                    document_title, section, source_type, document_kind, tags,
                    has_table, has_figure, patent_sections,
                    page_start, page_end, line_start, line_end,
                    title, headings, body, captions, tables, claims, examples
                )
                VALUES (
                    :repository_id, :document_id, :document_version_id, :chunk_id, :chunk_index,
                    :document_title, :section, :source_type, :document_kind, :tags,
                    :has_table, :has_figure, :patent_sections,
                    :page_start, :page_end, :line_start, :line_end,
                    :title, :headings, :body, :captions, :tables, :claims, :examples
                )
                """
            ),
            fields,
        )

    session.commit()
    return FullTextRebuildResponse(
        repository_id=repository_id,
        indexed_chunks=len(chunks),
        tokenizer=full_text_settings.tokenizer,
    )


def search_full_text(
    session: Session,
    repository_id: str,
    query: str,
    limit: int,
    filters: FullTextSearchFilters,
) -> FullTextSearchResponse | None:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    full_text_settings = RepositorySettings.model_validate(repository.settings.settings).full_text
    ensure_full_text_schema(session, full_text_settings)
    normalized_query = normalize_fts_query(query)
    if not normalized_query:
        return FullTextSearchResponse(
            query=query,
            normalized_query="",
            repository_id=repository_id,
            results=[],
        )

    where_clauses = [f"{FTS_TABLE} MATCH :query", "repository_id = :repository_id"]
    params: dict[str, Any] = {
        "query": normalized_query,
        "repository_id": repository_id,
        "limit": limit,
    }
    _append_filter(where_clauses, params, "document_id", filters.document_id)
    _append_filter(where_clauses, params, "section", filters.section)
    _append_filter(where_clauses, params, "source_type", filters.source_type)
    _append_filter(where_clauses, params, "document_kind", filters.document_kind)
    _append_bool_filter(where_clauses, params, "has_table", filters.has_table)
    _append_bool_filter(where_clauses, params, "has_figure", filters.has_figure)
    if filters.tag:
        _append_pipe_list_filter(where_clauses, params, "tags", "tag", filters.tag)
    if filters.patent_section:
        _append_pipe_list_filter(
            where_clauses,
            params,
            "patent_sections",
            "patent_section",
            filters.patent_section,
        )

    score_expression = "bm25({table}, {weights})".format(
        table=FTS_TABLE,
        weights=", ".join(str(FIELD_WEIGHTS[field]) for field in INDEXED_FIELDS),
    )
    rows = session.execute(
        text(
            f"""
            SELECT
                repository_id, document_id, document_version_id, chunk_id, chunk_index,
                document_title, section, source_type, document_kind, tags,
                has_table, has_figure, patent_sections,
                page_start, page_end, line_start, line_end,
                snippet({FTS_TABLE}, 19, '<mark>', '</mark>', '...', 24) AS snippet,
                {score_expression} AS score,
                title, headings, body, captions, tables, claims, examples
            FROM {FTS_TABLE}
            WHERE {" AND ".join(where_clauses)}
            ORDER BY score
            LIMIT :limit
            """
        ),
        params,
    ).mappings()

    results = [
        FullTextSearchResult(
            rank=rank,
            score=float(row["score"]),
            repository_id=str(row["repository_id"]),
            document_id=str(row["document_id"]),
            document_version_id=str(row["document_version_id"]),
            chunk_id=str(row["chunk_id"]),
            chunk_index=int(row["chunk_index"]),
            document_title=str(row["document_title"]),
            section=row["section"],
            page_start=row["page_start"],
            page_end=row["page_end"],
            line_start=row["line_start"],
            line_end=row["line_end"],
            snippet=str(row["snippet"]),
            matched_fields=_matched_fields(row, query),
            metadata={
                "source_type": row["source_type"],
                "document_kind": row["document_kind"],
                "tags": _split_tags(row["tags"]),
                "has_table": row["has_table"] == "1",
                "has_figure": row["has_figure"] == "1",
                "patent_sections": _split_tags(row["patent_sections"]),
            },
        )
        for rank, row in enumerate(rows, start=1)
    ]
    return FullTextSearchResponse(
        query=query,
        normalized_query=normalized_query,
        repository_id=repository_id,
        results=results,
    )


def ensure_full_text_schema(session: Session, settings: FullTextSettings) -> None:
    _drop_incompatible_fts_table(session)
    tokenizer = "porter unicode61" if settings.porter_stemming else settings.tokenizer
    prefix_clause = ", prefix='2 3 4'" if settings.prefix_index else ""
    session.execute(
        text(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(
                repository_id UNINDEXED,
                document_id UNINDEXED,
                document_version_id UNINDEXED,
                chunk_id UNINDEXED,
                chunk_index UNINDEXED,
                document_title UNINDEXED,
                section UNINDEXED,
                source_type UNINDEXED,
                document_kind UNINDEXED,
                tags UNINDEXED,
                has_table UNINDEXED,
                has_figure UNINDEXED,
                patent_sections UNINDEXED,
                page_start UNINDEXED,
                page_end UNINDEXED,
                line_start UNINDEXED,
                line_end UNINDEXED,
                title,
                headings,
                body,
                captions,
                tables,
                claims,
                examples,
                tokenize = '{tokenizer}'
                {prefix_clause}
            )
            """
        )
    )


def _drop_incompatible_fts_table(session: Session) -> None:
    columns = {
        str(row["name"])
        for row in session.execute(text(f"PRAGMA table_info({FTS_TABLE})")).mappings()
    }
    if columns and not REQUIRED_FTS_COLUMNS.issubset(columns):
        session.execute(text(f"DROP TABLE {FTS_TABLE}"))


def normalize_fts_query(query: str) -> str:
    terms = re.findall(r'"[^"]+"|\S+', query.strip())
    normalized = [_normalize_term(term) for term in terms]
    return " AND ".join(term for term in normalized if term)


def _normalize_term(term: str) -> str:
    stripped = term.strip()
    if not stripped:
        return ""
    if stripped.startswith('"') and stripped.endswith('"'):
        escaped = stripped[1:-1].replace('"', '""')
        return f'"{escaped}"'
    if re.search(r"[^A-Za-z0-9_]", stripped):
        escaped = stripped.replace('"', '""')
        return f'"{escaped}"'
    return stripped


def _append_filter(
    where_clauses: list[str],
    params: dict[str, Any],
    column: str,
    value: str | None,
) -> None:
    if value is None:
        return
    where_clauses.append(f"{column} = :{column}")
    params[column] = value


def _append_bool_filter(
    where_clauses: list[str],
    params: dict[str, Any],
    column: str,
    value: bool | None,
) -> None:
    if value is None:
        return
    where_clauses.append(f"{column} = :{column}")
    params[column] = "1" if value else "0"


def _append_pipe_list_filter(
    where_clauses: list[str],
    params: dict[str, Any],
    column: str,
    parameter: str,
    value: str,
) -> None:
    where_clauses.append(f"{column} LIKE :{parameter}")
    params[parameter] = f"%|{value}|%"


def _fields_for_chunk(
    chunk: DocumentChunk,
    document: Document,
    version: DocumentVersion,
) -> dict[str, Any]:
    metadata = chunk.extra_metadata or {}
    version_metadata = version.extra_metadata or {}
    section = chunk.section or ""
    structure_hints = _string_list(version_metadata.get("structure_hints"))
    patent_sections = _string_list(version_metadata.get("patent_section_hints"))
    field_text = _classify_body_text(chunk.text, section, metadata, structure_hints)
    tags = _tags(metadata)
    has_table = _has_structure_hint("tables", structure_hints, metadata, section)
    has_figure = _has_structure_hint("figures", structure_hints, metadata, section)
    return {
        "repository_id": chunk.repository_id,
        "document_id": chunk.document_id,
        "document_version_id": chunk.document_version_id,
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "document_title": document.display_name,
        "section": chunk.section,
        "source_type": version.source_type,
        "document_kind": version_metadata.get("document_kind"),
        "tags": "|" + "|".join(tags) + "|" if tags else "",
        "has_table": "1" if has_table else "0",
        "has_figure": "1" if has_figure else "0",
        "patent_sections": _pipe_list(patent_sections),
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "line_start": chunk.line_start,
        "line_end": chunk.line_end,
        "title": " ".join(
            str(value) for value in [document.display_name, version_metadata.get("title")] if value
        ),
        "headings": section,
        **field_text,
    }


def _classify_body_text(
    text_value: str,
    section: str,
    metadata: dict[str, Any],
    structure_hints: list[str],
) -> dict[str, str]:
    fields = {field: "" for field in INDEXED_FIELDS if field not in {"title", "headings"}}
    fields["body"] = text_value
    section_lower = section.lower()
    metadata_sections = {
        str(item).lower() for item in metadata.get("sections", []) if isinstance(item, str)
    }
    all_sections = {section_lower, *metadata_sections, *structure_hints}
    if any("claim" in value for value in all_sections):
        fields["claims"] = text_value
    if any("example" in value for value in all_sections):
        fields["examples"] = text_value
    if metadata.get("table_hints") or any("table" in value for value in all_sections):
        fields["tables"] = text_value
    if metadata.get("figure_hints") or any(
        value in {"figures", "captions"} or "caption" in value for value in all_sections
    ):
        fields["captions"] = text_value
    return fields


def _has_structure_hint(
    hint: str,
    structure_hints: list[str],
    metadata: dict[str, Any],
    section: str,
) -> bool:
    section_lower = section.lower()
    metadata_sections = _string_list(metadata.get("sections"))
    if hint == "tables" and metadata.get("table_hints"):
        return True
    if hint == "figures" and metadata.get("figure_hints"):
        return True
    return hint in structure_hints or any(
        hint.rstrip("s") in value for value in [section_lower, *metadata_sections]
    )


def _tags(metadata: dict[str, Any]) -> list[str]:
    raw_tags = metadata.get("tags", [])
    if not isinstance(raw_tags, list):
        return []
    return [str(tag) for tag in raw_tags if str(tag).strip()]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value if str(item).strip()]


def _pipe_list(values: list[str]) -> str:
    return "|" + "|".join(values) + "|" if values else ""


def _split_tags(value: Any) -> list[str]:
    if not value:
        return []
    return [tag for tag in str(value).split("|") if tag]


def _matched_fields(row: Any, original_query: str) -> list[str]:
    terms = [term.strip('"').lower() for term in re.findall(r'"[^"]+"|\S+', original_query)]
    matched: list[str] = []
    for field in INDEXED_FIELDS:
        value = str(row[field] or "").lower()
        if any(term and term in value for term in terms):
            matched.append(field)
    return matched or ["body"]
