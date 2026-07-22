# PRD 29: PRD13 Manual Acceptance Testing

**Status:** Backlog.

## Problem Statement

PRD13 is implemented and ready for final review, but its highest-risk behavior depends on local host state that should not become a default CI requirement: installed OCR binaries, optional RapidOCR availability, realistic scanned or mixed PDFs, local filesystem artifacts, full-text/vector rebuilds, and visual Source Viewer inspection.

Default deterministic tests cover parser routing, reprocess, stale index gates, OCR result normalization, synthetic OCR recovery, fallback warnings, chunking behavior, and frontend contracts. They intentionally do not prove that a real workstation can complete an end-to-end PRD13 acceptance pass with real OCR dependencies and representative documents.

The project needs a small PRD that turns the manual PRD13 acceptance pass into a repeatable checklist with evidence capture, so PRD13 can be closed confidently without making OCR engines, large PDFs, or private golden-corpus files part of ordinary CI.

## Solution

Create a manual acceptance-testing workflow for PRD13 that a maintainer can run on a local workstation with optional OCR dependencies installed. The workflow should specify prerequisites, representative document types, step-by-step app/API checks, expected observable outcomes, failure-note format, and the evidence required to accept or defer PRD13 closure.

The manual pass should exercise the whole researcher path: configure parser/chunking/OCR settings, upload born-digital, scanned, and mixed PDFs, run reprocess and OCR actions, inspect parser/OCR metadata in Source Viewer, rebuild full-text/vector indexes after freshness checks, verify retrieval sees OCR-derived chunks, export/recreate a repository, and record any host-specific caveats.

## User Stories

1. As a maintainer, I want a repeatable PRD13 manual test checklist, so that final acceptance does not depend on memory or ad hoc exploration.
2. As a researcher, I want PRD13 tested against real scanned and mixed PDFs, so that OCR recovery works beyond synthetic fixtures.
3. As a researcher, I want OCR dependency setup and skip rules documented, so that missing local binaries are reported clearly instead of blocking unrelated default tests.
4. As a maintainer, I want the checklist to distinguish deterministic CI coverage from manual OCR/golden-corpus coverage, so that the project keeps fast reliable defaults.
5. As a maintainer, I want parser/chunking settings tested through upload and reprocess, so that saved settings are proven operational in the app.
6. As a researcher, I want stale parser/chunk index gates tested manually, so that search does not silently index stale parse output after settings changes.
7. As a researcher, I want Source Viewer parser labels, OCR text, OCR warnings, and OCR-derived chunks checked visually, so that recovered text is auditable.
8. As a maintainer, I want RapidOCR fallback behavior checked when the dependency is available and skipped explicitly when it is not, so that optional fallback support remains honest.
9. As a researcher, I want OCR-derived chunks verified through full-text, vector, hybrid search, and chat context where local services are available, so that recovered documents become retrievable.
10. As a maintainer, I want export/recreate metadata checked after OCR and reprocess, so that parser fingerprints and OCR artifacts survive the portable repository workflow.
11. As a Windows or macOS tester, I want host-specific notes captured, so that dependency or path issues are not hidden inside a generic pass/fail result.
12. As a project owner, I want acceptance evidence recorded in docs or a local test report, so that PRD13 can be closed or deferred with clear rationale.

## Scope

- Manual test checklist for PRD13 parser routing, chunking, reprocess, OCR action, OCR fallback, Source Viewer review, stale index gates, retrieval, chat readiness where available, and export/recreate metadata.
- Prerequisite matrix for local dependencies such as Tesseract, OCRmyPDF if used, RapidOCR if installed, Qdrant, Ollama, and SentenceTransformers/cross-encoder caches.
- Representative document matrix covering born-digital PDFs, image-only/scanned PDFs, mixed PDFs, low-text PDFs, and at least one patent-like or scientific-paper example.
- Explicit skip rules for optional dependencies and host services.
- Evidence template for recording commands, app steps, document IDs, settings snapshots, screenshots or notes, search/chat queries, pass/fail decisions, and follow-up issues.
- Backlog/docs updates that make PRD29 the manual acceptance gate before PRD13 is marked complete.

## Non-Goals

- Adding OCR engines, large PDFs, private corpora, Qdrant, Ollama, or GPU checks to default CI.
- Rewriting PRD13 implementation behavior.
- Implementing PRD28 batch document actions.
- Implementing PRD14 table extraction, layout-aware scanned tables, formula recognition, or OCR quality evaluation beyond manual acceptance notes.
- Creating a hosted/cloud OCR path.
- Requiring every supported host to pass every optional dependency check before PRD13 can be accepted.

## Acceptance Criteria

- A manual PRD13 acceptance checklist exists with setup prerequisites, test data requirements, exact workflows, expected outcomes, and skip rules.
- The checklist covers upload/reprocess with `Auto` and at least one explicit parser route.
- The checklist covers fixed and recursive chunking outputs through app-visible behavior or inspectable metadata.
- The checklist covers stale parser/chunk freshness blocking before full-text/vector rebuilds and clean rebuild after reprocess.
- The checklist covers explicit OCR recovery for a `needs_ocr` or scanned document with real local OCR dependencies when available.
- The checklist covers recoverable missing-provider behavior when a configured OCR provider is unavailable.
- The checklist covers RapidOCR fallback when installed, or records an explicit skip when unavailable.
- The checklist covers Source Viewer display of parser route, dependency-version details, OCR text, confidence/warnings, and OCR-derived chunk labels.
- The checklist covers retrieval of OCR-derived chunks through full-text and at least one semantic/hybrid mode when vector services are available.
- The checklist covers export/recreate after PRD13 OCR/reprocess actions and verifies parser/OCR metadata survives.
- The checklist includes a compact evidence template suitable for a local report or PRD closeout note.
- Project docs explain that PRD13 remains ready for final review until PRD29 manual acceptance is completed or explicitly waived.

## Implementation Decisions

- Keep the checklist in the repository documentation rather than in `.plans/`, because future maintainers need the manual acceptance gate after the local plan context is gone.
- Treat manual checks as a complement to deterministic tests, not a replacement.
- Prefer observable app/API outcomes over inspecting private implementation details.
- Keep optional dependency checks granular: Tesseract/OCRmyPDF, RapidOCR, Qdrant, Ollama, and cross-encoder can each pass, fail, or be skipped independently.
- Record document provenance without committing restricted or private source documents.
- Preserve PRD13 ownership of parser/OCR behavior and PRD28 ownership of future batch actions.

## Testing Decisions

- Default automated tests remain unchanged and deterministic.
- Manual testing should use a small matrix of local documents selected for page text type and OCR risk, not a large benchmark corpus.
- Manual retrieval checks should use expected strings visible in recovered OCR text, plus a query that should retrieve an OCR-derived chunk.
- Manual UI checks should focus on user-visible labels, warnings, status transitions, and source navigation.
- Manual export/recreate checks should verify payload behavior through the app/API and inspectable recreated repository state, not internal serialization details.

## Out of Scope

PRD29 does not decide whether OCR quality is scientifically sufficient across all corpora. It only defines the final manual acceptance pass needed to close PRD13's implemented local parser/OCR behavior.

## Further Notes

If manual testing finds product defects, add focused remediation phases or follow-up PRDs instead of rewriting PRD13 history. PRD13 should move from ready for final review to complete only after the PRD29 checklist is passed, accepted with documented skips, or explicitly waived by the project owner.
