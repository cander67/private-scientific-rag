# Database Migrations

Alembic migrations live in this folder.

The first application migration is:

- `versions/20260630214430_repository_settings.py`: creates repositories, repository settings, and repository snapshots for PRD2 reproducibility work.

Run migrations locally with:

```bash
uv run alembic upgrade head
```

When adding or changing SQLAlchemy models, add the matching Alembic migration in the same change and verify it with `uv run alembic upgrade head`.
