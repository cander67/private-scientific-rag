# Tests

Tests are split by speed and dependency profile:

- `tests/unit/`: fast tests for pure functions, settings, models, and validation.
- `tests/integration/`: local app integration tests that avoid real LLM/model calls by default.

Live tests that require local services or models use the `live` marker and do not run by default.

PRD3 ingestion/source-inspection coverage is complete. Default CI does not read from `documents/golden_corpus/`; that directory is local/manual evaluation material. Tests use committed fixtures in `tests/fixtures/ingestion/` plus generated miniature PDFs for text-layer and image-only OCR-gate behavior. Larger files in `documents/golden_corpus/pdf/` and `documents/golden_corpus/ocr/` are useful for local/manual parser checks and future OCR work, but should not be default CI prerequisites unless they are intentionally copied into `tests/fixtures/` with redistribution approval.

PRD4 full-text search coverage includes unit tests for FTS query normalization and field weights, API integration coverage for rebuilding a repository index and searching citation-ready chunk results, metadata filter coverage, repository settings snapshot coverage, and CI exact-match recall evaluation.

Exact-match search fixtures live in `tests/fixtures/search/`. They cover formulas, abbreviations, identifiers, patent terms, and section headings, and require `recall@5` and `recall@10` to remain at `1.0` for the committed fixture set.

PRD5 vector search coverage uses deterministic fake embeddings and an in-memory vector store for ordinary CI. It covers vector rebuild/search API behavior, latest-index replacement metadata, full-text-equivalent filters, missing-index errors, and semantic recall evaluation. The committed semantic fixture is `tests/fixtures/search/prd5_semantic_fixture.json`.

PRD6 retrieval coverage includes deterministic integration tests for the unified retrieval API and evaluation comparison. The tests exercise full-text mode, vector mode with fake embeddings and an in-memory vector store, hybrid RRF mode, normalized score breakdowns, retrieval run/result persistence, max-five recent history retention, strategy validation, cross-encoder reranking through a fake provider, metadata boost scoring, and comparison metrics for full-text, vector, hybrid, and reranked hybrid. Unit tests cover RRF merging for sparse-only, dense-only, overlapping, adjusted-constant cases, reranker score composition, and missing cross-encoder setup guidance.

PRD7 chat coverage keeps CI deterministic by mocking the LLM at the chat boundary. Default tests cover repository prompt-library settings, prompt/context assembly, citation-token mapping, model registry responses, chat session/message persistence, hybrid retrieval wiring with a fake reranker, and assistant citation metadata persisted from a mocked LLM response. Live local LLM tests are separate opt-in commands.

PRD8 Prompt Sandbox coverage keeps CI deterministic by mocking the LLM at the sandbox boundary. Default tests cover sandbox prompt version validation, repository-scoped create/list/read/copy/delete behavior, side-by-side comparison persistence, progressive per-run comparison execution, prompt snapshot preservation, retrieved context snapshots, generated answers, citations, latency, and frontend contract coverage for the Prompt Sandbox view. Golden query datasets, aggregate retrieval metrics, and evidence-backed promotion to chat defaults are deferred to PRD18.

PRD9 export/import/recreate coverage includes the portable bundle contract, bundle validation, backend recreate execution, Export Center, and Recreate Repository UI contracts. Default tests cover deterministic source bundle paths and SHA-256 hashing, manifest schema validation, ZIP structure, default source inclusion, chat/retrieval/chunk/citation payload export, opt-in sandbox payload export, malformed/unsupported bundle rejection, missing payload detection, source hash mismatches, external source mapping failures, renamed-file warnings, missing model reports, parser fingerprints, exported count summaries, recreate into a new repository, recreate into an explicit empty repository, source-excluded recreate through external mappings, active chat/retrieval history remapping, deterministic full-text/vector rebuild reporting, validation display, blocked recreate, successful recreate progress, and final report display.

PRD9-focused deterministic commands:

```bash
uv run pytest tests/unit/test_export_bundle.py tests/integration/test_export_bundle_api.py
cd frontend
npm test
```

The cross-platform manual transfer checklist and warning glossary live in `docs/export_recreate.md`. Optional live checks for Qdrant, cross-encoder reranking, Ollama, and local RAG chat are listed below.

## Live tests

Default CI and `uv run pytest` exclude live tests. Run live checks only when the required local service or model is already available.

### Vector/Qdrant live smoke

Prerequisites:

- Qdrant is running at the configured `qdrant_url` (`http://127.0.0.1:6333` by default).
- The default SentenceTransformers embedding model can be loaded locally. If it is not cached, SentenceTransformers may download it during this explicit live run.

Run:

```bash
docker compose up -d qdrant
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_vector_live.py
```

### Cross-encoder live smoke

Prerequisites:

- The configured cross-encoder model is downloaded/cached locally. The default is `cross-encoder/ms-marco-MiniLM-L6-v2`.
- Retrieval API calls use `local_files_only=True` for cross-encoder reranking, so a missing model returns setup guidance instead of silently downloading during search.

Download/cache the default model:

```bash
uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')"
```

Run:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_cross_encoder_live.py
```

### Ollama chat live smoke

Prerequisites:

- Ollama is running at the configured `ollama_base_url` (`http://localhost:11434` by default).
- The default chat model is installed. The PRD7 default is `gemma3:4b`.

Download/cache the default chat model:

```bash
ollama pull gemma3:4b
```

Run the lightweight Ollama boundary check:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_ollama_live.py
```

### Local RAG chat live smoke

This slower check creates a tiny fixture repository, rebuilds deterministic in-memory full-text/vector test indexes, calls the real local Ollama chat model, and verifies that the assistant response stores mapped citations. It keeps embedding and reranking deterministic so failures point mostly at the local LLM setup and chat path.

Prerequisites are the same as the Ollama chat live smoke.

Run:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_chat_rag_live.py
```

### Prompt Sandbox live note

Prompt Sandbox product runs use the selected local chat model through the same local LLM boundary as Chat Workspace. PRD8 default CI uses mocked generation for determinism. A separate opt-in sandbox live smoke is deferred until PRD18 adds maintainer evaluation and promotion workflows.

Golden corpus planning currently lives in `documents/golden_corpus/golden_corpus_manifest.md`; `golden_corpus_manifest_v1.md` is a frozen historical copy.

Run all default tests:

```bash
uv run pytest
```

Run all default tests plus all opted-in live tests in one coverage pass:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m "not live or live"
```

Run backend tests by tier, including live tests when ready:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration
```

Run the full backend quality gate:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Run the full backend quality gate with live tests included in the same coverage report:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
RUN_LIVE_TESTS=1 uv run pytest -m "not live or live"
```

Run a specific group:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
```

Coverage is configured in `pyproject.toml`, results are output to the terminal and can also be found in `htmlcov/index.html`.
