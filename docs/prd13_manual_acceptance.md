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
| OCR acceptance workflow | `ready` | Run the workflow below after selecting documents and recording dependency status. |
| Export/recreate and evidence template | `ready` | Use the export/recreate checks and report template below for closeout evidence. |
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

## OCR Acceptance Workflow

Run this workflow through the app first. Use API probes only to capture precise metadata, stale conflicts, or failure details that are hard to preserve from the UI.

Before starting, record:

- Active repository ID and name.
- Host notes from the host matrix.
- Dependency statuses from the dependency matrix.
- Document matrix entries and target OCR/search strings.
- Current Settings / Models parser, chunking, OCR, full-text, vector, embedding, retrieval, chat, and reranking settings.

### 1. Parser and Chunking Settings

1. Open Settings / Models.
2. Save parser settings with structured parser `Auto` and fallback parser `Auto`.
3. Save chunking mode `recursive`, token size `512`, and overlap `64` unless the run intentionally uses different baseline settings.
4. Upload the born-digital PDF from Document Manager.
5. Open the document in Source Viewer.
6. Record parser route, parser version details, chunk count, chunking mode, token size, overlap, token count, tokenizer ID, tokenizer implementation, and any warnings.
7. Change Settings / Models to at least one explicit parser route such as PyMuPDF, pdfplumber, pypdf, or built-in fallback.
8. Reprocess the born-digital PDF.
9. Confirm the new current version records the explicit parser route or fallback decision.
10. Change chunking mode to `fixed`, reprocess, and confirm fixed token-window chunk metadata is visible.
11. Change chunking mode back to `recursive`, reprocess, and confirm recursive chunk metadata is visible.

Pass when upload and reprocess visibly use saved parser/chunking settings, and Source Viewer or inspection metadata shows both explicit parser routing and fixed/recursive chunking evidence.

API backstop:

```bash
curl -s "http://127.0.0.1:8000/repositories/$REPOSITORY_ID/documents/$DOCUMENT_ID"
curl -s -X POST "http://127.0.0.1:8000/repositories/$REPOSITORY_ID/documents/$DOCUMENT_ID/reprocess"
```

Record `document_id`, current `version_id`, parser route, parser fingerprint, changed fields, chunking mode, tokenizer metadata, warnings, and status.

### 2. Stale Parser/Chunk Rebuild Gate

1. With at least one parsed document present, rebuild full-text and vector indexes from Search Lab or Chat Workspace.
2. Change parser or chunking settings without reprocessing the current documents.
3. Attempt full-text rebuild.
4. Attempt vector rebuild when Qdrant and embeddings are available.
5. Confirm stale parser/chunk status blocks or warns before indexing stale chunks.
6. Reprocess stale documents through Document Manager, Search Lab, or Chat Workspace.
7. Rebuild full-text again and confirm the rebuild succeeds.
8. Rebuild vector again when dependencies are available and confirm the rebuild succeeds.

Pass when stale parser/chunk state is visible before rebuild, stale chunks are not silently indexed, and reprocess followed by rebuild produces fresh full-text and vector status where the required services are available.

API backstop:

```bash
curl -i -X POST "http://127.0.0.1:8000/repositories/$REPOSITORY_ID/full-text/rebuild"
curl -i -X POST "http://127.0.0.1:8000/repositories/$REPOSITORY_ID/vector/rebuild"
```

Record HTTP status, stale conflict text, stale document IDs, changed fields, and clean rebuild counts after reprocess.

### 3. OCR Recovery

1. Confirm the dependency matrix marks Tesseract CLI as `pass`; otherwise record this section as `skip` or `waived`.
2. In Settings / Models, set OCR provider to `ocrmypdf_tesseract`, language to the expected language such as `eng`, fallback provider to `rapidocr` when RapidOCR is available, and overwrite according to the run plan.
3. Upload the scanned/image-only or low-text PDF.
4. Confirm Document Manager or Source Viewer shows `needs_ocr`, low-text, image-heavy, or pending OCR state.
5. Run OCR from Source Viewer, Document Manager, or selected-document batch OCR.
6. Open Source Viewer after OCR completes.
7. Confirm page thumbnails remain available.
8. Confirm recovered OCR text is visible for the expected pages.
9. Confirm OCR confidence, warnings, provider metadata, rendered-image provenance, and OCR-derived chunk labels are visible or inspectable.
10. Confirm prior source files and prior parser/page artifacts remain available.

Pass when a real scanned, image-only, or low-text document recovers inspectable text and OCR-derived chunks without replacing or deleting source inspection artifacts.

API backstop:

```bash
curl -s -X POST "http://127.0.0.1:8000/repositories/$REPOSITORY_ID/documents/$SCANNED_DOCUMENT_ID/ocr"
curl -s "http://127.0.0.1:8000/repositories/$REPOSITORY_ID/documents/$SCANNED_DOCUMENT_ID"
```

Record OCR run status, provider, provider version, page numbers, warnings, confidence, OCR text snippets, OCR-derived chunk IDs, and rendered image hashes where present.

### 4. Missing Provider and RapidOCR Fallback

1. To verify missing-provider recovery, configure an OCR provider or fallback dependency that is unavailable on the current host, or run on a host where the selected provider is absent.
2. Run OCR on an eligible document.
3. Confirm the app records a recoverable missing-provider warning rather than deleting source files, prior chunks, page thumbnails, or previous OCR artifacts.
4. If RapidOCR is installed, set fallback provider to `rapidocr` and fallback enabled.
5. Use a low-confidence or low-text OCR case when available, or record that fallback was available but not triggered because baseline OCR quality was sufficient.
6. If RapidOCR is not installed, record RapidOCR as `skip` with the import command result from the dependency matrix.

Pass when missing-provider behavior is recoverable and RapidOCR fallback is either exercised, explicitly not triggered with reason, or explicitly skipped.

Record provider settings, missing-provider warning text, fallback provider, fallback decision metadata, and whether the original source/current version remained inspectable.

### 5. Source Viewer Audit

For each accepted OCR document, Source Viewer should provide enough evidence for a researcher to audit recovered text before trusting retrieval.

Verify and record:

- Parser name/route as the primary parser label.
- Dependency-version details as secondary metadata.
- Page thumbnail for the OCR page.
- OCR text for the page.
- OCR confidence when available.
- OCR warnings or missing-provider messages.
- OCR-derived chunk labels.
- Chunk page range, token count, tokenizer ID, tokenizer implementation, parser fingerprint, and OCR provider metadata.
- Stale or reprocess status after settings changes.

Pass when a reviewer can connect OCR text, page thumbnail, chunk, parser route, and provider/warning metadata without inspecting private implementation internals.

### 6. Retrieval and Chat Checks

1. Choose one target string visible in recovered OCR text and one natural-language query that should retrieve the OCR-derived chunk.
2. Rebuild full-text after OCR/reprocess.
3. Search full-text for the target string in Search Lab.
4. Confirm an OCR-derived chunk appears with document/source provenance.
5. When Qdrant and embeddings are available, rebuild vector and run vector or hybrid search for the natural-language query.
6. Confirm an OCR-derived chunk appears in vector or hybrid results.
7. When the cross-encoder cache is available, run reranked hybrid search or record reranking as skipped.
8. When Ollama and retrieval services are available, open Chat Workspace readiness, create or select a chat session, inspect draft context for the query, and confirm OCR-derived chunks appear in retrieved context.
9. Ask the chat question only if local model readiness is acceptable for the run; otherwise the context inspection is enough to record retrieval readiness.

Pass when full-text retrieves OCR-derived chunks, vector or hybrid retrieves OCR-derived chunks when dependencies are available, and Chat Workspace context includes OCR-derived chunks when Ollama/retrieval services are available.

API backstop:

```bash
curl -s -X POST "http://127.0.0.1:8000/repositories/$REPOSITORY_ID/full-text/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"TARGET_OCR_STRING","limit":5}'

curl -s -X POST "http://127.0.0.1:8000/repositories/$REPOSITORY_ID/retrieval/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"NATURAL_LANGUAGE_QUERY","mode":"hybrid","top_k":5}'
```

Record query text, result rank, document ID, chunk ID, OCR-derived metadata, retrieval mode, index status, and skipped service reasons.

## Export/Recreate Acceptance

Run this section after the OCR acceptance workflow has at least one current document with parser/chunk metadata and, when OCR dependencies are available, at least one OCR-derived chunk.

### 1. Export

1. Open Export Center for the accepted repository.
2. Review the repository counts, required models, settings snapshot, source-file options, and export warnings.
3. Export with source files included unless the source documents are private and the closeout run intentionally validates source-excluded behavior.
4. Store the ZIP outside Git and outside generated runtime directories that might be cleaned automatically.
5. Record the export filename, timestamp, repository ID, source-inclusion setting, document count, chunk count, retrieval/chat inclusion state, and any warnings.

Pass when the export completes and the exported summary reflects the accepted parser/OCR repository state.

Do not commit the export ZIP.

### 2. Recreate Validation

1. Open Recreate Repository.
2. Select the exported ZIP.
3. Provide available-model names if the run is checking model availability warnings.
4. Provide source mappings only when the export excluded source files.
5. Run validation before recreate.
6. Confirm validation reports settings, source hashes, parser fingerprints, tokenizer metadata, required models, and blocking source issues accurately.
7. Resolve blocking validation errors or record them as `fail` or `defer` with enough detail to reproduce.

Pass when validation either succeeds or reports expected non-blocking warnings with clear source/model/parser metadata.

### 3. Recreate Execution

1. Recreate into a new repository unless the run explicitly uses an empty target repository.
2. Confirm the recreated repository becomes selectable in the app.
3. Inspect the recreated document list and Source Viewer for the accepted OCR document.
4. Confirm parser route, parser fingerprint metadata, chunk tokenizer metadata, OCR page metadata, OCR warnings, OCR-derived chunk labels, and source hashes survive recreate where expected.
5. Review full-text rebuild results from the recreate report or rebuild full-text manually after recreate.
6. Rebuild vector search when Qdrant and embeddings are available, then run the OCR target query from the workflow.
7. Record any expected host-specific differences, such as dependency-version differences or skipped vector/chat rebuilds.

Pass when recreated repository state preserves enough parser/OCR/chunk/source metadata to audit the OCR-derived content, and index rebuild reports are clean or have documented optional-service skips.

API backstop:

```bash
curl -s -X POST "http://127.0.0.1:8000/repositories/$REPOSITORY_ID/exports/bundle?include_sources=true" \
  --output /tmp/prd13-manual-acceptance.zip

curl -s -X POST "http://127.0.0.1:8000/repositories/recreate/bundle/validate" \
  -F "file=@/tmp/prd13-manual-acceptance.zip"

curl -s -X POST "http://127.0.0.1:8000/repositories/recreate/bundle" \
  -F "file=@/tmp/prd13-manual-acceptance.zip" \
  -F "repository_name=PRD13 manual acceptance recreate"
```

Record validation status, recreated repository ID, recreated document IDs, recreated version IDs, index counts, warning text, and skipped service reasons.

## Evidence Report Template

Create the report as a local note, PR comment, or PRD closeout comment. Do not commit private PDFs, OCR outputs, screenshots, export ZIPs, local indexes, model files, or unrestricted absolute paths if the report will become public.

```markdown
# PRD13 Manual Acceptance Report

Date:
Tester:
Branch/commit:
Host OS:
Python / uv / Node:
Backend URL:
Frontend URL:
Repository ID:
Repository name:

## Closeout Decision

Decision: pass | pass with skips | defer | waived
Rationale:
Follow-up issue(s) or remediation plan:

## Dependency Status

| Dependency | Status | Version / command output | Notes |
| --- | --- | --- | --- |
| Python app dependencies |  |  |  |
| Frontend dependencies |  |  |  |
| Tesseract CLI |  |  |  |
| RapidOCR |  |  |  |
| Qdrant |  |  |  |
| SentenceTransformers embedding model |  |  |  |
| Ollama runtime and chat model |  |  |  |
| Cross-encoder cache |  |  |  |

## Document Matrix

| Document type | Status | Local label / filename | Document ID | Version ID | Source hash | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Born-digital PDF |  |  |  |  |  |  |
| Image-only or scanned PDF |  |  |  |  |  |  |
| Mixed PDF |  |  |  |  |  |  |
| Low-text PDF |  |  |  |  |  |  |
| Patent-like or scientific-paper PDF |  |  |  |  |  |  |

## Settings Snapshot

Parser:
Chunking:
OCR:
Full-text:
Vector / embedding:
Retrieval / reranking:
Chat:

## OCR Acceptance Workflow Evidence

Parser/chunking result:
Stale rebuild gate result:
OCR recovery result:
Missing-provider result:
RapidOCR fallback result:
Source Viewer audit result:
Full-text retrieval result:
Vector/hybrid retrieval result:
Chat context result:

Target OCR string(s):
Natural-language query:
Observed result ranks / chunk IDs:
Screenshots or local notes:

## Export/Recreate Evidence

Export filename/location:
Source inclusion:
Validation result:
Recreated repository ID:
Recreated document/version IDs:
Parser/OCR metadata preserved:
Full-text/vector rebuild report:
Warnings/skips:

## Final Notes

Host-specific caveats:
Deferred work:
Owner acceptance or waiver:
```

Closeout outcomes:

- `pass`: Required manual OCR acceptance areas passed, with optional checks either passing or not applicable.
- `pass with skips`: Required behavior passed and optional dependency/service/document gaps are documented with reasons.
- `defer`: A product defect, acceptance gap, or missing representative run should be fixed before PRD13 is closed.
- `waived`: The project owner explicitly accepts closing PRD13 without running one or more checks.

## Closeout Rule

PRD13 remains ready for final review until this checklist is completed, accepted with documented skips, or explicitly waived by the project owner. Do not mark PRD13 complete solely because deterministic tests pass or because optional OCR checks are unavailable on one workstation.

If manual testing finds product defects, preserve PRD13 history and add a focused remediation phase or follow-up PRD. The local report should name the failed step, host details, dependency status, document ID or source hash, expected behavior, observed behavior, and the follow-up issue or plan item.
