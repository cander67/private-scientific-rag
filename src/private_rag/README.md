# Backend Package

The backend package contains the FastAPI app, configuration, database wiring, and future RAG services.

Initial module boundaries:

- `api/`: FastAPI application and routes.
- `core/`: settings and shared application infrastructure.
- `db/`: SQLAlchemy base, engine, sessions, and future models.
- `services/`: local service checks and future domain services.

PRD1 keeps behavior intentionally thin. PRD2 starts the repository/settings schema.
