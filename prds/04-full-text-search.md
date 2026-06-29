# PRD 4: Full-Text Search

## Goal

Implement inspectable full-text search with SQLite FTS5 for exact scientific terms, identifiers, formulas, abbreviations, and patent language.

## User Stories

- As a researcher, I can search exact terms and rare identifiers.
- As a researcher, I can see why a result matched.
- As a researcher, I can filter full-text results by repository, document, section, table, figure, tag, or patent metadata where available.

## Scope

- SQLite FTS5 schema and migrations.
- Sparse indexing service.
- Field weighting for title, headings, body, captions, tables, claims, and examples.
- Full-text query API.
- Search result metadata and BM25 score display.
- Rebuild sparse index per repository.

## Non-Goals

- External search engine.
- Vector search.
- Hybrid search.

## Acceptance Criteria

- FTS5 index can be rebuilt for one repository.
- Exact identifiers, abbreviations, formulas, patent terms, and section headings are retrievable in the golden corpus.
- Results include BM25 score, rank, matched document/chunk metadata, and citation-ready provenance.
- Full-text settings are stored in repository settings and snapshots.

## Test Plan

- Unit test tokenizer/normalization behavior.
- Unit test field weight configuration.
- Integration test full-text search on golden corpus.
- Evaluation records recall@5 and recall@10 for exact-match queries.

## Documentation References

- `tests/README.md` for test organization.
- SQLite FTS5 documentation: https://www.sqlite.org/fts5.html
- SQLite documentation: https://www.sqlite.org/docs.html
- Azure Search relevance overview: https://learn.microsoft.com/en-us/azure/search/search-relevance-overview
