# Database Migrations

Alembic migrations live in this folder.

Application migrations:

- `versions/20260630214430_repository_settings.py`: creates repositories, repository settings, and repository snapshots for PRD2 reproducibility work.
- `versions/20260701101500_document_ingestion.py`: creates document, version, chunk, artifact, and processing-event tables for PRD3 ingestion/source inspection.
- `versions/20260706120000_full_text_search.py`: creates the SQLite FTS5 `full_text_chunks` virtual table for PRD4 sparse full-text search, including unindexed metadata columns for document kind, tags, table/figure hints, patent sections, and citation provenance.
- `versions/20260707100000_vector_search.py`: creates the `embedding_runs` table for PRD5 latest vector index metadata, including repository, provider/model, vector settings, Qdrant collection, status, chunk count, and settings snapshot.

Run migrations locally with:

```bash
uv run alembic upgrade head
```

When adding or changing SQLAlchemy models, add the matching Alembic migration in the same change and verify it with `uv run alembic upgrade head`.
