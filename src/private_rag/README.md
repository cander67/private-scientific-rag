# Backend Package

The backend package contains the FastAPI app, configuration, database wiring, repository metadata, and future RAG services.

Module boundaries:

- `api/`: FastAPI application and routes.
- `core/`: settings and shared application infrastructure.
- `db/`: SQLAlchemy base, engine, and session wiring.
- `repositories/`: repository SQLAlchemy models, Pydantic settings/manifest schemas, and reproducibility service logic.
- `services/`: local service checks and future domain services.
- Future ingestion modules should keep original source files, parsed artifacts, chunks, and provenance metadata distinct.

Current API surface:

- `GET /health`: local app and dependency health check.
- `GET /repositories/default`: creates or returns the default repository with validated settings.
- `GET /repositories/{repository_id}/settings`: loads repository settings.
- `PUT /repositories/{repository_id}/settings`: validates and saves repository settings.
- `GET /repositories/{repository_id}/manifest`: exports a reproducibility manifest and stores a snapshot.
- `POST /repositories/recreate/validate`: reports missing source files, missing models, and incompatible settings before recreate work begins.

PRD2 owns repository-aware settings and reproducibility. PRD3 will add local document ingestion and source inspection for PDFs, text, markdown, annotations, and user-uploaded patent PDFs. Bulk patent-data feeds and multi-jurisdiction patent parsing are deferred to PRD12.
