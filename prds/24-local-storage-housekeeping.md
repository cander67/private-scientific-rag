# PRD 24: Local Storage Provenance and Housekeeping

**Status:** Backlog.

## Problem Statement

User testing surfaced confusion about generated local files under `data/repositories` and `.qdrant/collections`. Users can see many files appear after importing documents, parsing sources, rebuilding indexes, exporting, or running Qdrant, but the app does not clearly explain what created them, whether they are source data or derived data, and which files are safe to remove.

PRD19 added guarded repository deletion and local reset flows, but users still need a non-destructive way to inspect storage provenance, understand growth over time, detect orphaned artifacts, and clean up safe derived data without manually browsing backend directories.

## Solution

Add a Local Storage and Housekeeping surface that inventories app-managed files, derived artifacts, export bundles, database records, and Qdrant collections by repository. The workflow should explain where each category comes from, whether it is source or derived state, whether it is included in exports, and what cleanup actions are safe.

The first implementation should focus on visibility, provenance, and safe cleanup of orphaned or derived artifacts. Destructive repository deletion remains in Repository Administration, while immutable embedding-index deletion remains in PRD16.

## User Stories

1. As a researcher, I want to see what `data/repositories` contains, so that generated files do not feel mysterious.
2. As a researcher, I want to know which files are app-managed source copies, parsed text, page images, derived chunks, exports, or temporary artifacts, so that I know what is safe to clean.
3. As a researcher, I want to see which workflow created each storage category, so that I understand why files appeared after ingestion, OCR, export, or vector rebuild.
4. As a researcher, I want to see Qdrant collection names mapped back to repositories and embedding runs, so that `.qdrant/collections` is understandable.
5. As a researcher, I want the app to identify orphaned files or Qdrant collections, so that failed experiments do not accumulate forever.
6. As a researcher, I want to preview cleanup of safe derived artifacts, so that I can recover disk space without deleting source documents.
7. As a researcher, I want cleanup to preserve external source files and local model caches, so that housekeeping does not remove expensive or irreplaceable local assets.
8. As a researcher, I want clear explanations when Qdrant is unavailable, so that collection inventory failures are actionable.
9. As a maintainer, I want storage inventory to be repository-scoped by default, so that cleanup reports have a small blast radius.
10. As a maintainer, I want cleanup policies to classify generated files by category, so that future OCR, table extraction, and bulk-patent PRDs can plug into the same model.
11. As a maintainer, I want orphan detection to be deterministic in tests, so that the app can safely distinguish database-backed files from unknown files.
12. As a maintainer, I want documentation to explain that `.qdrant/collections` is Qdrant's own persistence directory, so users do not manually edit it.

## Implementation Decisions

- Add a Local Storage or Housekeeping section reachable from Repository Administration or Settings / Models.
- Build storage inventory from database records plus filesystem walks under the configured app data directory. Do not inspect arbitrary user directories except for already-recorded external source references.
- Classify artifacts into source copies, derived parser artifacts, full-text state, vector/Qdrant state, export bundles, temporary files, unknown app-directory files, external references, and model caches.
- Treat source copies, external references, and model caches as preserve-by-default categories.
- Provide preview-first cleanup for orphaned or derived artifacts. Reuse PRD19's cleanup-plan/result vocabulary where possible.
- Map Qdrant collections to known embedding runs when Qdrant is reachable and report unmatched collections as orphan candidates, not automatic deletion targets.
- Include disk-size estimates where reasonably available, but do not make exact size accounting a blocker for cleanup.
- Add documentation that explains where files come from: ingestion creates repository source/derived artifacts, parsing/OCR/table extraction creates derived files, export creates portable bundles, and Qdrant persists vectors under its own storage directory.
- Keep broad machine cleanup, Docker volume management, and model-cache deletion out of scope.

## Testing Decisions

- Unit tests should cover storage classification and orphan-detection rules using isolated temporary directories.
- Integration tests should create database-backed app-managed files, external references, unknown files, and fake Qdrant collection metadata, then verify inventory and cleanup previews.
- Integration tests should verify cleanup removes only explicitly selected derived/orphan categories and preserves source copies unless the user chooses a repository deletion flow.
- Frontend contract tests should cover storage inventory categories, provenance labels, preview-before-cleanup behavior, preserved categories, Qdrant unavailable messaging, and links to Repository Administration.
- Live Qdrant inventory checks should remain opt-in and run only against disposable local collections.

## Out of Scope

- Deleting entire repositories; PRD19 owns that destructive workflow.
- Deleting local Ollama, SentenceTransformers, Hugging Face, or other model caches.
- Directly editing Qdrant storage files under `.qdrant/collections`.
- Full immutable embedding-index selection, comparison, or archival; PRD16 owns that lifecycle.
- Background scheduled cleanup jobs.

## Further Notes

- This PRD is a user-testing follow-up to PRD19. PRD19 made cleanup safe; this PRD makes local storage understandable before cleanup is needed.
- Future parsing PRDs should register new generated-artifact categories with this inventory model instead of adding one-off cleanup guidance.
