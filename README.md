# Private Scientific RAG

[![CI](https://github.com/cander67/private-scientific-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/cander67/private-scientific-rag/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Private Scientific RAG is a local-first research workbench for building multimodal retrieval-augmented generation over focused scientific and technical document collections.

The project is being built for local operation on macOS, Windows-native Python/Ollama, and Linux/Ubuntu. The first version is a single-user localhost app with a FastAPI backend, React/Vite frontend, SQLite metadata store, SQLite FTS5 full-text search, Qdrant vector search, and local Ollama/SentenceTransformers models.

## Current Status

PRD1 through PRD8 are complete and closed. The project now has the local app foundation, repository settings/reproducibility, document ingestion/source inspection, inspectable SQLite FTS5 search, dense vector search, hybrid Reciprocal Rank Fusion, selectable reranking, retrieval evaluation, local Ollama-backed retrieval-augmented chat with citations, and a Prompt Sandbox for prompt/retrieval/model comparisons. PRD9 export/import/recreate is in progress.

Later PRDs include OCR execution (PRD13), structured table extraction (PRD14), bulk patent downloads/raw patent-data feeds (PRD12), and clearer chunk-level versus document-level search labels (PRD17). Support for additional embedding models and immutable document storage are also planned.

The current scaffold provides:

- FastAPI backend shell with `/health`.
- Repository settings API for default repository creation, settings updates, manifest export, and recreate validation.
- Document upload, PDF parser fallback chain, page-thumbnail generation, parsing/chunking, source inspection, reprocess, and delete API for PDF, TXT, Markdown, and ANN files.
- SQLite FTS5 rebuild and full-text search API for repository chunks, with BM25 scores, snippets, matched fields, metadata filters, citation-ready provenance, and CI exact-match recall evaluation.
- Qdrant-backed vector index rebuild and vector search API for repository chunks, with local SentenceTransformers MiniLM embeddings, latest-index replacement, metadata filters, embedding run metadata, and CI semantic recall evaluation with deterministic fake embeddings.
- Unified retrieval search API for full-text, vector, and hybrid modes, with candidate-pool/RRF/reranker settings capture, Reciprocal Rank Fusion score breakdowns, selectable cross-encoder/metadata-boost reranking, and max-five recent retrieval history persistence.
- Local RAG chat API for repository-scoped chat sessions, chat-owned retrieval settings, Ollama model smoke checks, readiness checks, structured citation mapping, and persisted chat messages.
- Prompt Sandbox API for repository-scoped sandbox prompt versions, copy-to/from chat prompt library, prompt deletion, persisted sandbox runs, progressive side-by-side retrieval comparisons, context snapshots, citations, latency, and status.
- Portable repository ZIP export/recreate bundle API with validation, a versioned manifest, settings, prompt library, document/chunk metadata, chat and retrieval history, citations, selected source files, external source mapping, rebuilt full-text/vector indexes, and opt-in sandbox data.
- Deterministic comparison evaluation for full-text, vector, hybrid, and reranked hybrid retrieval, plus opt-in live Qdrant and cross-encoder checks.
- React/Vite frontend document manager, source inspector, Search Lab, Chat Workspace, Prompt Sandbox, and Export Center for full-text, vector, hybrid, reranked retrieval inspection, local cited chat, prompt/retrieval/model comparison, and portable ZIP export, including PDF thumbnail inspection for `needs_ocr` documents with no chunks.
- SQLAlchemy/Alembic migration wiring for repository settings, document ingestion, vector embedding runs, and retrieval history/results.
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

Vector rebuilds use the repository embedding/vector settings. The default embedding model is `sentence-transformers/all-MiniLM-L6-v2` with 384-dimensional cosine vectors.

Unified retrieval defaults to a candidate pool of `top_k * 5` and an RRF constant of `60`; both can be adjusted per request. Cross-encoder reranking uses `cross-encoder/ms-marco-MiniLM-L6-v2` by default and requires the model to be downloaded into the local SentenceTransformers cache. See [test documentation](tests/README.md) for the download command and separate deterministic, live-vector, and live-cross-encoder test commands.

Chat uses its own retrieval settings rather than inheriting Search Lab state. It does not rebuild indexes automatically. Before chatting, rebuild the full-text and vector indexes for the repository and confirm the local Ollama model is reachable from the Chat Workspace readiness panel. The default chat model is `gemma3:4b`; default chat retrieval is hybrid with cross-encoder reranking. Repository chat prompts live in repository settings, and the UI keeps chat-owned retrieval controls, readiness checks, session management, and citation source navigation inside Chat Workspace.

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
