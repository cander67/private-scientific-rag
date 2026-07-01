# Private Scientific RAG

[![CI](https://github.com/cander67/private-scientific-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/cander67/private-scientific-rag/actions/workflows/ci.yml)

Private Scientific RAG is a local-first research workbench for building multimodal retrieval-augmented generation over focused scientific and technical document collections.

The project is being built for local operation on macOS, Windows-native Python/Ollama, and Linux/Ubuntu. The first version is a single-user localhost app with a FastAPI backend, React/Vite frontend, SQLite metadata store, SQLite FTS5 full-text search, Qdrant vector search, and local Ollama/SentenceTransformers models.

## Current Status

PRD1 foundation is complete, PRD2 repository settings work has started, and the first PRD3 document ingestion/source inspection slice is implemented. PRD3 assumes users can upload patent PDFs of interest, while bulk patent downloads and raw patent-data feeds are deferred to PRD12.

The current scaffold provides:

- FastAPI backend shell with `/health`.
- Repository settings API for default repository creation, settings updates, manifest export, and recreate validation.
- Document upload, PDF parser fallback chain, parsing/chunking, source inspection, reprocess, and delete API for PDF, TXT, Markdown, and ANN files.
- React/Vite frontend document manager and source inspector.
- SQLAlchemy/Alembic migration wiring with the first repository/settings tables.
- Qdrant Docker Compose service.
- Pytest, Ruff, Mypy, and CI configuration.
- Public-repo safety defaults.
- A versioned golden corpus plan and scaffold under `documents/golden_corpus/` for PRD3 ingestion smoke tests.

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

Apply database migrations:

```bash
uv run alembic upgrade head
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

The golden corpus folder is for curated test planning and safe fixtures only. Do not commit private, licensed, or restricted research documents.

The `example_code/` folder is local inspiration code and should not be committed.

## Documentation

- [PRD backlog](prds/README.md)
- [Golden corpus manifest](documents/golden_corpus/golden_corpus_manifest_v1.md)
- [Test documentation](tests/README.md)
- [Backend documentation](src/private_rag/README.md)
- [Frontend documentation](frontend/README.md)
- [Public repo checklist](docs/public_repo_checklist.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
