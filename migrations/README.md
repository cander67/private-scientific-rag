# Database Migrations

Alembic migrations live in this folder.

Application migrations:

- `versions/20260630214430_repository_settings.py`: creates repositories, repository settings, and repository snapshots for PRD2 reproducibility work.
- `versions/20260701101500_document_ingestion.py`: creates document, version, chunk, artifact, and processing-event tables for PRD3 ingestion/source inspection.

Run migrations locally with:

```bash
uv run alembic upgrade head
```

When adding or changing SQLAlchemy models, add the matching Alembic migration in the same change and verify it with `uv run alembic upgrade head`.
