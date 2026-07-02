# Tests

Tests are split by speed and dependency profile:

- `tests/unit/`: fast tests for pure functions, settings, models, and validation.
- `tests/integration/`: local app integration tests that avoid real LLM/model calls by default.

Live tests that require local services or models should use the `live` marker and should not run by default.

Golden corpus planning currently lives in `documents/golden_corpus/golden_corpus_manifest_v1.md`. PRD3 uses this corpus for ingestion/source-inspection smoke tests, with patent coverage limited to user-uploaded PDFs. The `documents/golden_corpus/ocr/` fixtures include both existing OCR-text-layer PDFs and PNG round-trip PDFs that should be marked `needs_ocr` while still showing page thumbnails. Bulk patent-data feeds are deferred to PRD12.

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
