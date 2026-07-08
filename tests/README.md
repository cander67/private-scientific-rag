# Tests

Tests are split by speed and dependency profile:

- `tests/unit/`: fast tests for pure functions, settings, models, and validation.
- `tests/integration/`: local app integration tests that avoid real LLM/model calls by default.

Live tests that require local services or models should use the `live` marker and should not run by default.

PRD3 ingestion/source-inspection coverage is complete. Default CI does not read from `documents/golden_corpus/`; that directory is local/manual evaluation material. Tests use committed fixtures in `tests/fixtures/ingestion/` plus generated miniature PDFs for text-layer and image-only OCR-gate behavior. Larger files in `documents/golden_corpus/pdf/` and `documents/golden_corpus/ocr/` are useful for local/manual parser checks and future OCR work, but should not be default CI prerequisites unless they are intentionally copied into `tests/fixtures/` with redistribution approval.

PRD4 full-text search coverage includes unit tests for FTS query normalization and field weights, API integration coverage for rebuilding a repository index and searching citation-ready chunk results, metadata filter coverage, repository settings snapshot coverage, and CI exact-match recall evaluation.

Exact-match search fixtures live in `tests/fixtures/search/`. They cover formulas, abbreviations, identifiers, patent terms, and section headings, and require `recall@5` and `recall@10` to remain at `1.0` for the committed fixture set.

PRD5 vector search coverage uses deterministic fake embeddings and an in-memory vector store for ordinary CI. It covers vector rebuild/search API behavior, latest-index replacement metadata, full-text-equivalent filters, missing-index errors, and semantic recall evaluation. The committed semantic fixture is `tests/fixtures/search/prd5_semantic_fixture.json`; real SentenceTransformers/Qdrant smoke checks should stay small and use the `live` marker when added.

PRD6 retrieval coverage starts with deterministic integration tests for the unified retrieval API. The tests exercise full-text mode, vector mode with fake embeddings and an in-memory vector store, normalized score breakdowns, retrieval run/result persistence, and max-five recent history retention. Hybrid RRF, reranking strategies, and opt-in real cross-encoder checks will extend this coverage in later PRD6 slices.

Golden corpus planning currently lives in `documents/golden_corpus/golden_corpus_manifest.md`; `golden_corpus_manifest_v1.md` is a frozen historical copy.

Run all default tests:

```bash
uv run pytest
```

Run the full backend quality gate:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Run a specific group:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
```

Coverage is configured in `pyproject.toml`, results are output to the terminal and can also be found in `htmlcov/index.html`.
