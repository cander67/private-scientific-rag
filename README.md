# Private Scientific RAG

[![CI](https://github.com/cander67/private-scientific-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/cander67/private-scientific-rag/actions/workflows/ci.yml)

Private Scientific RAG is a local-first research workbench for building multimodal retrieval-augmented generation over focused scientific and technical document collections.

The project is being built for local operation on macOS, Windows-native Python/Ollama, and Linux/Ubuntu. The first version is a single-user localhost app with a FastAPI backend, React/Vite frontend, SQLite metadata store, SQLite FTS5 full-text search, Qdrant vector search, and local Ollama/SentenceTransformers models.

## Current Status

PRD1 foundation is in progress. The current scaffold provides:

- FastAPI backend shell with `/health`.
- React/Vite frontend shell.
- SQLAlchemy/Alembic migration wiring.
- Qdrant Docker Compose service.
- Pytest, Ruff, Mypy, and CI configuration.
- Public-repo safety defaults.

Public repository target: `cander67/private-scientific-rag`.

## Local Setup

Install prerequisites:

- Python 3.11
- `uv`
- Node.js 22 or newer
- Docker Desktop on macOS/Windows, or Docker Engine on Linux
- Ollama for local model runtime

Install backend dependencies:

```bash
uv sync --all-extras --dev
```

Start Qdrant:

```bash
docker compose up -d qdrant
```

Run the backend:

```bash
uv run uvicorn private_rag.api.app:app --reload
```

Install and run the frontend:

```bash
cd frontend
npm install
npm run dev
```

## Checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

Frontend:

```bash
cd frontend
npm run build
```

## Local Data

Runtime data belongs outside Git:

- `data/`
- `models/`
- `exports/`
- `.qdrant/`
- private document corpora

The `example_code/` folder is local inspiration code and should not be committed.

## Documentation

- [PRD backlog](prds/README.md)
- [Test documentation](tests/README.md)
- [Backend documentation](src/private_rag/README.md)
- [Frontend documentation](frontend/README.md)
- [Public repo checklist](docs/public_repo_checklist.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
