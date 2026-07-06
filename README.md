# Private Scientific RAG

[![CI](https://github.com/cander67/private-scientific-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/cander67/private-scientific-rag/actions/workflows/ci.yml)

Private Scientific RAG is a local-first research workbench for building multimodal retrieval-augmented generation over focused scientific and technical document collections.

The project is being built for local operation on macOS, Windows-native Python/Ollama, and Linux/Ubuntu. The first version is a single-user localhost app with a FastAPI backend, React/Vite frontend, SQLite metadata store, SQLite FTS5 full-text search, Qdrant vector search, and local Ollama/SentenceTransformers models.

## Current Status

PRD1, PRD2, PRD3, and PRD4 are complete. The project now has the local app foundation, repository settings/reproducibility, document ingestion/source inspection, and inspectable SQLite FTS5 full-text search for exact scientific terms, identifiers, formulas, abbreviations, and patent language.

Full OCR execution is planned in PRD13, structured table extraction in PRD14, and bulk patent downloads/raw patent-data feeds in PRD12.

The current scaffold provides:

- FastAPI backend shell with `/health`.
- Repository settings API for default repository creation, settings updates, manifest export, and recreate validation.
- Document upload, PDF parser fallback chain, page-thumbnail generation, parsing/chunking, source inspection, reprocess, and delete API for PDF, TXT, Markdown, and ANN files.
- SQLite FTS5 rebuild and full-text search API for repository chunks, with BM25 scores, snippets, matched fields, metadata filters, citation-ready provenance, and CI exact-match recall evaluation.
- React/Vite frontend document manager, source inspector, and Search Lab for full-text query inspection, including PDF thumbnail inspection for `needs_ocr` documents with no chunks.
- SQLAlchemy/Alembic migration wiring for repository/settings and document-ingestion tables.
- Qdrant Docker Compose service.
- Pytest, Ruff, Mypy, and CI configuration.
- Public-repo safety defaults.
- Local/manual golden corpus documentation under `documents/golden_corpus/`, with CI-safe fixtures under `tests/fixtures/`.

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

Defaults to `http://127.0.0.1:8000`
Docs available at `http://127.0.0.1:8000/docs`

Install and run the frontend:

```bash
cd frontend
npm install
npm run dev
```

Defaults to `http://127.0.0.1:5173`

## Checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Frontend:

```bash
cd frontend
npm run build
npm test
```

## Local Data

Runtime data belongs outside Git:

- `data/`
- `models/`
- `exports/`
- `.qdrant/`
- private document corpora

The `documents/` folder is a local/manual workspace. Do not commit private, licensed, downloaded, generated, or restricted research documents. Use `scripts/prepare_golden_corpus.sh` to recreate the golden-corpus folder layout and optional public candidates. CI tests use `tests/fixtures/`, not `documents/`.

The `example_code/` folder is local inspiration code and should not be committed.

## Documentation

- [PRD backlog](prds/README.md)
- [Golden corpus manifest](documents/golden_corpus/golden_corpus_manifest.md)
- [Documents workspace](documents/README.md)
- [Test documentation](tests/README.md)
- [Backend documentation](src/private_rag/README.md)
- [Frontend documentation](frontend/README.md)
- [Public repo checklist](docs/public_repo_checklist.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
