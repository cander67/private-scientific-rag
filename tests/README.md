# Tests

Tests are split by speed and dependency profile:

- `tests/unit/`: fast tests for pure functions, settings, models, and validation.
- `tests/integration/`: local app integration tests that avoid real LLM/model calls by default.

Live tests that require local services or models should use the `live` marker and should not run by default.

PRD3 ingestion/source-inspection coverage is complete. Default CI does not read from `documents/golden_corpus/`; that directory is local/manual evaluation material. Tests use committed fixtures in `tests/fixtures/ingestion/` plus generated miniature PDFs for text-layer and image-only OCR-gate behavior. Larger files in `documents/golden_corpus/pdf/` and `documents/golden_corpus/ocr/` are useful for local/manual parser checks and future OCR work, but should not be default CI prerequisites unless they are intentionally copied into `tests/fixtures/` with redistribution approval.

Golden corpus planning currently lives in `documents/golden_corpus/golden_corpus_manifest.md`; `golden_corpus_manifest_v1.md` is a frozen historical copy.

Run all default tests:

```bash
uv run pytest
```

Run a specific group:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
```

Coverage is configured in `pyproject.toml`, results are output to the terminal and can also be found in `htmlcov/index.html`.
