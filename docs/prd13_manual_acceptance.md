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
| Dependency, host, and document matrix | `pending` | Filled in during PRD29 Phase 2. |
| OCR acceptance workflow | `pending` | Filled in during PRD29 Phase 3. |
| Export/recreate and evidence template | `pending` | Filled in during PRD29 Phase 4. |
| Final PRD13 closeout decision | `pending` | `pass`, `pass with skips`, `defer`, or `waived`. |

## Closeout Rule

PRD13 remains ready for final review until this checklist is completed, accepted with documented skips, or explicitly waived by the project owner. Do not mark PRD13 complete solely because deterministic tests pass or because optional OCR checks are unavailable on one workstation.

If manual testing finds product defects, preserve PRD13 history and add a focused remediation phase or follow-up PRD. The local report should name the failed step, host details, dependency status, document ID or source hash, expected behavior, observed behavior, and the follow-up issue or plan item.
