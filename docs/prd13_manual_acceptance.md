# PRD13 Manual Acceptance Checklist

PRD29 defines the manual acceptance gate for PRD13 parser selection, OCR, and page-image text recovery. Use this checklist after deterministic tests pass and before moving PRD13 from ready for final review to complete.

This checklist is intentionally manual. It exercises local OCR binaries, optional RapidOCR fallback, realistic scanned or mixed PDFs, local model/service readiness, Source Viewer inspection, retrieval, chat context, and export/recreate behavior that should not become ordinary CI requirements.

## Outcome Vocabulary

Use the same result vocabulary in the checklist and local evidence report:

- `pass`: The behavior was exercised and matched the expected observable outcome.
- `pass with skips`: Required PRD13 behavior passed, and optional host/service checks were skipped with a clear reason.
- `skip`: The check depends on an optional local dependency, host service, or private document that is unavailable for this run.
- `fail`: The behavior was exercised and did not match the expected outcome, or a required dependency for the selected run failed unexpectedly.
- `defer`: The run found a product defect or acceptance gap that should be handled by a focused remediation phase or follow-up PRD before PRD13 is closed.
- `waived`: The project owner explicitly accepts not running one or more manual checks for this closeout.

## CI Boundary

Default deterministic checks remain the baseline for implementation confidence:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
cd frontend
npm run build
npm test
```

These checks cover parser routing, reprocess behavior, stale parser/chunk gates, OCR result normalization, synthetic OCR recovery, fallback warnings, chunking behavior, export/recreate contracts, and frontend state contracts with deterministic fixtures and mocked local services.

The manual checklist covers the remaining local acceptance risk:

- Real OCR provider availability and host-specific setup.
- Representative born-digital, scanned, mixed, low-text, patent-like, or scientific PDFs.
- Visual Source Viewer review of parser labels, page images, OCR text, warnings, confidence, and OCR-derived chunks.
- Full-text/vector/hybrid retrieval of OCR-derived chunks when local services are available.
- Chat Workspace readiness/context checks when Ollama and retrieval indexes are available.
- Export/recreate behavior with real parser/OCR metadata and source hashes.

## Checklist Status

Record one status per section:

| Section | Status | Notes |
| --- | --- | --- |
| Dependency, host, and document matrix | `ready` | Use the dependency, host, and document tables below before running OCR workflow checks. |
| OCR acceptance workflow | `pending` | Filled in during PRD29 Phase 3. |
| Export/recreate and evidence template | `pending` | Filled in during PRD29 Phase 4. |
| Final PRD13 closeout decision | `pending` | `pass`, `pass with skips`, `defer`, or `waived`. |

## Dependency Matrix

Complete this matrix at the start of each manual run. Optional dependencies can be skipped independently; missing one optional service should not block unrelated checks.

| Dependency | Required For | Verify | Pass | Fail | Skip |
| --- | --- | --- | --- | --- | --- |
| Python app dependencies | All backend and parser checks | `uv sync --all-extras --dev` and `uv run pytest tests/unit/test_ocr.py tests/unit/test_ingestion_parser.py` | Commands complete or environment is already synced and targeted tests pass. | Install or targeted tests fail unexpectedly. | Do not skip for a PRD13 closeout run. |
| Frontend dependencies | UI inspection through Document Manager, Source Viewer, Search Lab, Chat Workspace, Export Center, and Recreate Repository | `cd frontend && npm install` if needed, then `npm run build` or app starts with `npm run dev` | Build or app startup succeeds. | Build/startup fails unexpectedly. | Only skip if the run is explicitly API-only and UI acceptance is waived. |
| Tesseract CLI | Baseline local OCR provider shown in settings as `ocrmypdf_tesseract` | `tesseract --version` | Command prints a version and the app OCR action can invoke it. | Command is present but OCR action fails unexpectedly. | Command is unavailable; record baseline OCR recovery as skipped unless another explicit OCR provider is selected for this run. |
| RapidOCR | Optional fallback provider | `uv run python -c "import rapidocr_onnxruntime"` or `uv run python -c "import rapidocr"` | Import succeeds and fallback behavior is exercised or reported as not triggered because OCR quality is sufficient. | Import succeeds but fallback selection fails unexpectedly. | Neither import succeeds; record RapidOCR fallback as skipped. |
| Qdrant | Vector and hybrid retrieval of OCR-derived chunks | `docker compose up -d qdrant`, then use Settings / Models readiness or vector rebuild | Qdrant readiness passes and vector rebuild/search can run. | Qdrant is expected to be available but readiness, rebuild, or search fails. | Qdrant is not installed/running for this workstation; full-text checks still run. |
| SentenceTransformers embedding model | Vector rebuild/search when embedding provider is `sentence_transformers` | Settings / Models embedding readiness, or `uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"` | Model loads locally and vector rebuild/search can run. | Model is expected to be available but loading or embedding fails. | Model cache is unavailable; vector/hybrid checks may be skipped unless Ollama embeddings are selected and ready. |
| Ollama runtime and chat model | Chat Workspace readiness/context checks | `ollama list`, Settings / Models chat readiness, or Chat Workspace readiness | Runtime responds and the configured chat model is available. | Runtime/model is expected to be available but readiness or chat request fails. | Ollama is not running or model is not pulled; retrieval checks still run. |
| Cross-encoder cache | Reranked hybrid retrieval and default reranker smoke | `uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')"` | Model loads locally and reranked hybrid search can run. | Model is expected to be available but reranking fails. | Cache is unavailable; use non-reranked full-text/vector/hybrid checks and record reranking skip. |

## Host Notes

Record the host at the top of the local evidence report:

| Host | Notes To Capture |
| --- | --- |
| macOS | CPU architecture, Python version, `uv` version, Node version, Docker Desktop status, Ollama status, `tesseract --version`, and whether any Homebrew paths or app permissions affected OCR. |
| Windows-native Python/Ollama | Windows version, native Python path, PowerShell command variants used, Docker Desktop status, Ollama for Windows status, `tesseract --version`, and any path quoting or source-file mapping issues. Do not rely on WSL paths for a native app run. |
| Linux/Ubuntu | Distribution/version, Python version, Docker Engine/Desktop status, Ollama status, `tesseract --version`, package source for Tesseract, and any filesystem permission issues for uploaded sources or rendered OCR images. |

## Representative Document Matrix

Choose a small local corpus. Do not commit private PDFs, OCR outputs, screenshots, export ZIPs, local indexes, or model files. Prefer documents in `documents/` or another local workspace, and record enough provenance to reproduce the run without exposing restricted content.

| Document Type | Required? | What It Proves | Provenance To Record | Pass | Skip |
| --- | --- | --- | --- | --- | --- |
| Born-digital PDF | Yes | `Auto` preserves normal parser behavior and does not force unnecessary OCR. | Local path, filename, document ID, source SHA-256 if visible, page count, redistribution status, selected parser settings. | Upload produces parsed text/chunks and Source Viewer shows parser route without OCR-required status. | Do not skip for a PRD13 closeout run. |
| Image-only or scanned PDF | Yes when Tesseract is available | A `needs_ocr` or low/no-text document can recover searchable OCR text. | Local path, filename, document ID, source SHA-256 if visible, scanned pages used, OCR language/settings, redistribution status. | OCR action stores recovered text, warnings/confidence metadata, and OCR-derived chunks. | Tesseract unavailable, or no redistributable/private scanned sample is available; record explicit skip or waiver. |
| Mixed PDF | Yes when available | Page routing distinguishes born-digital, scanned, and mixed pages without OCRing every page unnecessarily. | Local path, filename, document ID, source SHA-256 if visible, page numbers for text-heavy and scan-heavy pages. | Source Viewer or API metadata shows different page OCR classifications and OCR only where needed. | No mixed sample is available; document why and use separate born-digital plus scanned samples. |
| Low-text PDF | Recommended | Low native text or poor extraction is visible and recoverable instead of silently producing weak retrieval. | Local path, filename, document ID, source SHA-256 if visible, expected low-text pages or expected extracted string. | Upload/reprocess surfaces low-text or OCR-needed state, and OCR/reprocess behavior is explicit. | Skip if the scanned sample already covers low-text behavior and note the overlap. |
| Patent-like or scientific-paper PDF | Yes for final PRD13 closeout unless waived | OCR/parser behavior works on representative research material, not only toy fixtures. | Local path, filename, document ID, source SHA-256 if visible, title or non-sensitive label, document kind, redistribution status, target OCR/search strings. | At least one expected recovered string is inspectable and retrievable after OCR/index rebuild. | No suitable local document is available; project owner must accept a documented skip or waiver. |

## Closeout Rule

PRD13 remains ready for final review until this checklist is completed, accepted with documented skips, or explicitly waived by the project owner. Do not mark PRD13 complete solely because deterministic tests pass or because optional OCR checks are unavailable on one workstation.

If manual testing finds product defects, preserve PRD13 history and add a focused remediation phase or follow-up PRD. The local report should name the failed step, host details, dependency status, document ID or source hash, expected behavior, observed behavior, and the follow-up issue or plan item.
