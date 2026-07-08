# Database Migrations

Alembic migrations live in this folder.

Application migrations:

- `versions/20260630214430_repository_settings.py`: creates repositories, repository settings, and repository snapshots for PRD2 reproducibility work.
- `versions/20260701101500_document_ingestion.py`: creates document, version, chunk, artifact, and processing-event tables for PRD3 ingestion/source inspection.
- `versions/20260706120000_full_text_search.py`: creates the SQLite FTS5 `full_text_chunks` virtual table for PRD4 sparse full-text search, including unindexed metadata columns for document kind, tags, table/figure hints, patent sections, and citation provenance.
- `versions/20260707100000_vector_search.py`: creates the `embedding_runs` table for PRD5 latest vector index metadata, including repository, provider/model, vector settings, Qdrant collection, status, chunk count, and settings snapshot.
- `versions/20260708100000_retrieval_runs.py`: creates PRD6 `retrieval_runs` and `retrieval_results` tables. Runs store mode, query, filters, top-k, candidate pool, RRF, embedding/vector, reranker, metadata-boost, and settings-snapshot fields. Results store chunk/document identity, final rank and score, source ranks, matched fields, metadata, and score breakdowns. Application persistence retains the five newest runs per repository and deletes older runs with their cascading result rows.

Run migrations locally with:

```bash
uv run alembic upgrade head
```

When adding or changing SQLAlchemy models, add the matching Alembic migration in the same change and verify it with `uv run alembic upgrade head`.

To verify the complete migration chain against a new SQLite database without touching local application data:

```bash
PRIVATE_RAG_DATABASE_URL=sqlite:////tmp/private-rag-migration-check.db uv run alembic upgrade head
```
