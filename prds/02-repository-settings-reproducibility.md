# PRD 2: Repository Settings and Reproducibility

## Goal

Create repository-aware settings, snapshots, and manifests so every local RAG run is reproducible and portable across macOS, Windows, and Linux.

## User Stories

- As a researcher, I can create or use a default repository.
- As a researcher, I can save retrieval, model, parser, prompt, and export settings per repository.
- As a researcher, I can export a manifest that describes how the repository should be rebuilt.
- As a developer, I can validate whether a repository can be recreated before rebuilding indexes.

## Scope

- Repository data model.
- Repository settings model.
- Repository snapshot model.
- Repository manifest model.
- Settings API.
- Recreate validation API skeleton.
- Settings UI mockup alignment.

## Key Settings

- Chunk size, overlap, and chunking mode.
- Structured parser and fallback parser.
- SQLite FTS5 settings.
- Qdrant collection/vector settings.
- Embedding provider and model.
- Reranking strategy and model.
- Ollama chat model.
- Prompt version.
- Export options.

## Acceptance Criteria

- Default repository is created on first run.
- Repository settings can be saved, loaded, updated, and validated.
- Manifest export includes parser, chunking, full-text, vector, embedding, reranking, prompt, and model settings.
- Recreate validation reports missing source files, missing models, or incompatible settings clearly.
- Settings are stored in SQLite through SQLAlchemy models and Alembic migrations.

## Test Plan

- Unit test settings validation.
- Unit test manifest serialization.
- Integration test repository creation and settings round-trip.
- Integration test recreate validation with missing files and missing models.

## Documentation References

- `README.md` for local configuration.
- `src/private_rag/README.md` for backend module boundaries.
- SQLAlchemy documentation: https://docs.sqlalchemy.org/
- Alembic documentation: https://alembic.sqlalchemy.org/
- Pydantic Settings documentation: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
