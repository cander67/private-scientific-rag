# Private Scientific RAG

[![CI](https://github.com/cander67/private-scientific-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/cander67/private-scientific-rag/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Private Scientific RAG is a local-first research workbench for building multimodal retrieval-augmented generation over focused scientific and technical document collections.

The project is being built for local operation on macOS, Windows-native Python/Ollama, and Linux/Ubuntu. The first version is a single-user localhost app with a FastAPI backend, React/Vite frontend, SQLite metadata store, SQLite FTS5 full-text search, Qdrant vector search, and local Ollama/SentenceTransformers models.

## Current Status

PRD1 through PRD9, PRD15, and PRD19 through PRD22 are complete and closed. PRD13 Parser Selection, OCR, and Page-Image Text Recovery is ready for final review after parser routing, reprocess, stale-index freshness gates, local OCR recovery, RapidOCR fallback, and documentation preparation; it is not marked complete until user acceptance. PRD23 Settings Model Catalog and Collection Guardrails is ready for final review after baseline implementation and user-testing remediation around model/runtime readiness, Windows Ollama embedding behavior, Chat Workspace embedding visibility, and explanatory docs. PRD26 Repository Loading and Parser Controls is ready for review with explicit repository-switch loading states and catalog-backed parser controls. The project now has the local app foundation, repository settings/reproducibility, document ingestion/source inspection, inspectable SQLite FTS5 search, dense vector search with additional local embedding models, hybrid Reciprocal Rank Fusion, selectable reranking, retrieval evaluation, local Ollama-backed retrieval-augmented chat with citations and expanded local chat model registry/readiness support, a Prompt Sandbox for prompt/retrieval/model comparisons, portable export/recreate workflows for moving repositories across supported local hosts, guarded repository administration/reset workflows, a repository-scoped Settings / Models manager with catalog-backed model, parser, and OCR guardrails, and a dashboard home surface for repository status and workflow navigation.

Later PRDs include structured table extraction (PRD14), bulk patent downloads/raw patent-data feeds (PRD12), clearer chunk-level versus document-level search labels (PRD17), chat context inspection (PRD25), and immutable document storage. Immutable multi-index embedding comparison remains PRD16 scope.

The app currently provides:

- FastAPI backend shell with `/health`.
- Repository settings API for default repository creation, settings updates, settings impact analysis, explicit model/service readiness checks, manifest export, and recreate validation.
- Repository dashboard summary API for repository-scoped counts, full-text/vector index readiness, local service/model readiness, active configuration, warnings, and recent activity.
- Document upload, PDF parser fallback chain, page-thumbnail generation, parsing/chunking, source inspection, reprocess, explicit OCR recovery, OCR fallback, and delete API for PDF, TXT, Markdown, and ANN files.
- SQLite FTS5 rebuild and full-text search API for repository chunks, with BM25 scores, snippets, matched fields, metadata filters, citation-ready provenance, and CI exact-match recall evaluation.
- Qdrant-backed vector index rebuild and vector search API for repository chunks, with local SentenceTransformers and Ollama embedding model support, latest-index replacement, metadata filters, embedding run metadata, and CI semantic recall/model-comparison evaluation with deterministic fake embeddings.
- Unified retrieval search API for full-text, vector, and hybrid modes, with candidate-pool/RRF/reranker settings capture, Reciprocal Rank Fusion score breakdowns, selectable cross-encoder/metadata-boost reranking, and max-five recent retrieval history persistence.
- Local RAG chat API for repository-scoped chat sessions, chat-owned retrieval settings, Ollama model smoke checks, readiness checks, structured citation mapping, and persisted chat messages.
- Prompt Sandbox API for repository-scoped sandbox prompt versions, copy-to/from chat prompt library, prompt deletion, persisted sandbox runs, progressive side-by-side retrieval comparisons, context snapshots, citations, latency, and status.
- Portable repository ZIP export/recreate bundle API with validation, a versioned manifest, settings, prompt library, document/chunk metadata, chat and retrieval history, citations, selected source files, external source mapping, rebuilt full-text/vector indexes, and opt-in sandbox data.
- Repository Administration API and UI for local inventory, cleanup previews, guarded one-repository deletion, guarded clear-all reset, preserved external files/model caches, incomplete Qdrant cleanup reporting, and retrying leftover vector collection cleanup.
- Deterministic comparison evaluation for full-text, vector, hybrid, reranked hybrid retrieval, and supported embedding models, plus opt-in live Qdrant, SentenceTransformers, Ollama, and cross-encoder checks.
- React/Vite frontend Repository Dashboard, document manager, source inspector, Search Lab, Chat Workspace, Prompt Sandbox, Settings / Models, Export Center, and Recreate Repository views for home/status navigation, settings management, full-text, vector, hybrid, reranked retrieval inspection, local cited chat, prompt/retrieval/model comparison, portable ZIP export, and bundle validation/recreate, including PDF thumbnail inspection, reprocess status/actions, OCR recovery actions, recovered page text, OCR-derived chunk labels, and repository OCR quality controls.
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

PowerShell:

```powershell
uv sync --all-extras --dev
```

Apply database migrations:

```bash
uv run alembic upgrade head
```

PowerShell:

```powershell
uv run alembic upgrade head
```

Start Qdrant:

```bash
docker compose up -d qdrant
```

PowerShell:

```powershell
docker compose up -d qdrant
```

Vector rebuilds use the repository embedding/vector settings and replace the repository's latest Qdrant collection after validation. Supported embedding options include the MiniLM baseline, `sentence-transformers/all-mpnet-base-v2`, `embeddinggemma:300m`, and `qwen3-embedding:8b`; see [embedding model documentation](docs/embedding_models.md) for dimensions, local setup, GPU/CPU behavior, provider tradeoffs, and the PRD15/PRD16 index boundary. The default embedding model is `sentence-transformers/all-MiniLM-L6-v2` with 384-dimensional cosine vectors.

Unified retrieval defaults to a candidate pool of `top_k * 5` and an RRF constant of `60`; both can be adjusted per request. Cross-encoder reranking uses `cross-encoder/ms-marco-MiniLM-L6-v2` by default and requires the model to be downloaded into the local SentenceTransformers cache. See [test documentation](tests/README.md) for the download command and separate deterministic, live-vector, and live-cross-encoder test commands.

Chat uses its own retrieval settings rather than inheriting Search Lab state. It does not rebuild indexes automatically. Before chatting, rebuild the full-text and vector indexes for the repository and confirm the local Ollama model is reachable from the Chat Workspace readiness panel. The default chat model is `gemma3:4b`; default chat retrieval is hybrid with cross-encoder reranking. Repository chat prompts live in repository settings, and the UI keeps chat-owned retrieval controls, readiness checks, session management, and citation source navigation inside Chat Workspace.

Settings / Models is the repository-scoped place to edit parser/chunking, OCR, full-text, vector/embedding, reranking, chat prompt/model, and export defaults. It validates settings before save, records reproducibility snapshots through the repository settings API, previews rebuild/workflow impact, and only runs Qdrant/Ollama/SentenceTransformers/cross-encoder readiness checks when the user explicitly starts them. Parser settings use catalog-backed choices instead of free-text fields: `Auto`, PyMuPDF, Docling, pdfplumber, pypdf, built-in fallback, the OCR-needed gate, OCRmyPDF/Tesseract, and RapidOCR are represented as validated repository settings. Upload/reprocess parser routing, OCR execution, RapidOCR fallback, OCR quality controls, and stale parser/chunk index freshness are implemented for PRD13 final review. OCR settings control primary provider, optional fallback provider, language, confidence threshold, minimum recovered text length, max pages, and overwrite behavior; optional OCR providers report recoverable warnings when missing rather than becoming default CI requirements. PRD23 adds catalog-backed chat, embedding, and reranker choices; known embedding models derive locked vector dimensions and compatible distance choices; custom local models remain available behind explicit advanced paths. Ollama embedding readiness checks the configured runtime through `/api/embed`, falls back to `/api/embeddings` for compatible older runtimes, sends warm-up `keep_alive`, and is only considered ready after a vector with the expected dimension is returned. Missing runtime/model guidance avoids Bash-only assumptions so Windows users get usable setup wording.

Repository Dashboard is the default home surface. Empty hash, `#home`, and `#repository-dashboard` all open the same view. It summarizes the active repository, counts documents/chunks/chats/retrieval/sandbox/export/recreate history, shows full-text and vector states as missing/partial/stale/ready, surfaces Qdrant/chat/embedding/reranker readiness using the Settings / Models vocabulary, lists active configuration defaults, and routes warnings, quick actions, and recent activity entries to workflow-owned pages. Repository switches clear repository-scoped views and show loading, loaded, failed, or empty status in the header and dashboard while documents, settings, model catalog, chats, readiness, prompts, and summaries refresh. Dashboard actions are navigation-only; destructive repository cleanup lives in Repository Administration.

Run the backend:

```bash
uv run uvicorn private_rag.api.app:app --reload
```

PowerShell:

```powershell
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

PowerShell:

```powershell
Set-Location frontend
npm install
npm run dev
Set-Location ..
```

Defaults to `http://127.0.0.1:5173`

## Checks

Backend:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

PowerShell:

```powershell
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

PowerShell:

```powershell
Set-Location frontend
npm run build
npm test
Set-Location ..
```

## Local Data

Runtime data belongs outside Git:

- `data/`
- `models/`
- `exports/`
- `.qdrant/`
- private document corpora

The `documents/` folder is a local/manual workspace. Do not commit private, licensed, downloaded, generated, or restricted research documents. On macOS/Linux or Git Bash, use `scripts/prepare_golden_corpus.sh` to recreate the golden-corpus folder layout and optional public candidates. On Windows PowerShell, create the local folders with:

```powershell
$folders = "checks", "markdown", "notes", "ocr", "patents_uploaded", "pdf", "source_bundles", "text"
$folders | ForEach-Object { New-Item -ItemType Directory -Force -Path "documents/golden_corpus/$_" | Out-Null }
New-Item -ItemType File -Force -Path "documents/golden_corpus/source_bundles/.gitkeep", "documents/golden_corpus/text/.gitkeep" | Out-Null
```

CI tests use `tests/fixtures/`, not `documents/`.

The `example_code/` folder is local inspiration code and should not be committed.

## Documentation

- [PRD backlog](prds/README.md)
- [Golden corpus manifest](documents/golden_corpus/golden_corpus_manifest.md)
- [Documents workspace](documents/README.md)
- [Test documentation](tests/README.md)
- [Embedding model guide](docs/embedding_models.md)
- [Chunking modes guide](docs/chunking_modes.md)
- [Backend documentation](src/private_rag/README.md)
- [Frontend documentation](frontend/README.md)
- [Export/recreate transfer guide](docs/export_recreate.md)
- [Public repo checklist](docs/public_repo_checklist.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
