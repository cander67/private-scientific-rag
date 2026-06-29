# PRD 1: Local Project Foundation

## Goal

Create the public-ready project foundation for a local, cross-platform scientific RAG app.

## User Stories

- As a developer, I can clone the repo and start the backend and frontend locally.
- As a maintainer, I can run tests, linting, and type checks before every PR.
- As a public GitHub project owner, I can publish the repo without committing secrets, private documents, generated indexes, or model files.
- As a future host, I can see setup notes for macOS, Windows-native Python/Ollama, and Linux/Ubuntu.

## Decisions

- Frontend: React/Vite.
- Backend: FastAPI.
- Python environment: `uv`.
- Database/migrations: SQLite, SQLAlchemy, Alembic.
- Vector service: Qdrant server mode through Docker Compose.
- Public repo should be created before PR1 implementation work, after public-readiness checks.

## Scope

- Project folder structure.
- Backend app shell and health endpoint.
- Frontend app shell.
- Qdrant Docker Compose service definition.
- Test/lint/type tooling.
- `.gitignore`, `.env.example`, README, license decision, and CI skeleton.
- Public repo checklist.

## Non-Goals

- Real ingestion.
- Real search.
- Real LLM calls.
- User authentication.

## UX and Mockups

- Mockups are static HTML in `mockups/`.
- All proposed mockups must be approved before backend implementation begins.
- The production frontend starts only after mockup approval.

## Acceptance Criteria

- `uv sync` succeeds.
- Backend health endpoint returns app version, data path, and local-only status.
- React/Vite frontend starts locally.
- Qdrant service can be started with Docker Compose or reports a clear unavailable state.
- Alembic can create an initial empty migration.
- Tests, linting, and type checks run locally.
- `.gitignore` excludes `.env`, local data, generated indexes, exports, model files, and private corpora.
- Public repo checklist exists before the first commit.

## Test Plan

- Unit test app settings loading.
- Integration test health endpoint.
- Smoke test Qdrant configuration check.
- CI runs lint, type check, and tests.

## Documentation References

- `README.md` for local setup and checks.
- `docs/public_repo_checklist.md` for first public commit readiness.
- `tests/README.md` for test layout and conventions.
- `src/private_rag/README.md` for backend module boundaries.
- `frontend/README.md` for React/Vite setup.
- FastAPI documentation: https://fastapi.tiangolo.com/
- Vite documentation: https://vite.dev/
- SQLAlchemy documentation: https://docs.sqlalchemy.org/
- Alembic documentation: https://alembic.sqlalchemy.org/
- Qdrant documentation: https://qdrant.tech/documentation/overview/

## GitHub Timing

Create the public GitHub repo before implementation PRs begin. The first commit should contain only public-safe planning/scaffold files. Run a staged secret/content sweep before committing and confirm the intended GitHub account before publishing.
