# PRD 28: Document Manager Preview and Batch Actions

**Status:** Backlog.

## Problem Statement

PRD3 delivered document ingestion, source inspection, single-document reprocess, and delete. PRD13 adds parser/OCR execution and document-level OCR actions. In hands-on use, Document Manager still creates friction for routine corpus maintenance.

The selected-document metadata card is useful, but users currently have to inspect/open a document path to reliably select and act on it. The document table does not behave like a selectable list, and actions such as reprocess, OCR, and delete are one-document-at-a-time. For repositories with many uploaded papers or scanned patent PDFs, this makes common cleanup workflows unnecessarily repetitive.

## Solution

Add a Document Manager interaction layer for lightweight document metadata preview and selected-document batch actions. A row click should select a document and immediately populate the metadata card from list-summary data. Full Source Viewer inspection should remain available for chunk/page review, but it should not be required just to inspect document metadata or enable eligible document actions.

Add explicit multi-document selection and batch action APIs for reprocess, OCR, and delete. Batch actions should return per-document outcomes so partial success, skipped items, missing OCR dependencies, missing source files, and wrong-repository protection are visible.

This PRD is a follow-up to closed PRD3 and in-progress PRD13. It does not reopen PRD3; it addresses product friction discovered after the original Document Manager and Source Viewer behavior shipped.

## User Stories

1. As a researcher, I can click a document row and immediately see document metadata, so that I do not have to open Source Viewer just to inspect the selected document.
2. As a researcher, I can still open the selected document in Source Viewer when I need chunks, pages, OCR text, or provenance details.
3. As a researcher, I can select multiple documents, so that batch maintenance is not repetitive.
4. As a researcher, I can reprocess selected documents after parser or chunking settings change, so that stale documents can be refreshed together.
5. As a researcher, I can run OCR on selected OCR-eligible documents, so that scanned corpus cleanup is practical.
6. As a researcher, I can delete selected documents without using delete all, so that targeted cleanup is safe.
7. As a researcher, I can see which selected documents were completed, skipped, or failed, so that partial batch results are understandable.
8. As a researcher, I can see why a document is ineligible for OCR or reprocess, so that disabled actions do not feel arbitrary.
9. As a maintainer, I want batch routes to reuse single-document service behavior, so that batch actions do not create divergent semantics.
10. As a maintainer, I want deterministic tests for partial batch outcomes and UI state, so that destructive and expensive actions remain safe.

## Scope

- Document Manager row-click selection that updates the selected-document metadata card without requiring full inspection.
- Selected-document action enablement based on document summary/current-version state rather than inspection payload presence.
- Multi-select checkboxes, selected-count state, and select-visible/clear-selection controls.
- Batch action toolbar for reprocess, OCR, and delete.
- Batch reprocess API over explicit selected document IDs.
- Batch OCR API over explicit selected document IDs, using PRD13 OCR semantics and dependency behavior.
- Batch delete API over explicit selected document IDs, distinct from delete all.
- Per-document batch result schema with action, document ID, status, optional version metadata, warnings, and error message.
- UI summaries for all-success, mixed-success, skipped, failed, missing-source, missing-dependency, and ineligible outcomes.
- Refresh behavior after batch actions so the table, selected document card, stale status, and Source Viewer links stay coherent.

## Non-Goals

- Background job queues for long-running batch actions.
- Automatic OCR on upload.
- Delete all or repository reset changes; PRD19 owns destructive repository administration.
- Full storage cleanup or orphan detection; PRD24 owns housekeeping.
- Changing parser/OCR implementation details owned by PRD13.
- Rebuilding full-text/vector indexes automatically after reprocess or OCR.

## Acceptance Criteria

- Clicking a document row selects it and updates the selected-document metadata card immediately from `DocumentRead.current_version`.
- Opening Source Viewer still loads full `DocumentInspection` for chunks, pages, OCR text, and provenance.
- Reprocess/OCR/delete actions for a selected single document do not require a prior Source Viewer inspection unless the action truly needs deeper data.
- Users can select one, many, all visible, or none of the documents in the current filtered view.
- Batch reprocess returns per-document completed, skipped, failed, and missing-source outcomes.
- Batch OCR returns per-document completed, skipped, failed, ineligible, and missing-dependency outcomes.
- Batch delete deletes only selected document IDs and returns per-document deleted or failed outcomes.
- Batch APIs validate repository ownership for every selected document.
- One recoverable document failure does not abort unrelated documents in the same batch.
- Delete-selected confirmation states the exact selected count and is clearly distinct from delete all.
- After batch actions, Document Manager refreshes the document list, selected-document card, and status messages.
- Tests cover row preview, selection behavior, all-success batches, partial failures, wrong-repository protection, ineligible OCR, missing dependencies, and destructive-action confirmation.

## Implementation Decisions

- Keep existing single-document routes intact for direct actions.
- Prefer small batch service wrappers that call existing single-document operations and collect outcomes.
- Make batch delete explicit and selection-scoped. Do not overload the existing delete-all route.
- Use document summary metadata for preview; use inspection only for Source Viewer and chunk/page-specific interactions.
- Keep batch action results structured enough for frontend display and future export/audit use, but do not create a generalized job system until batch duration requires it.
- Surface downstream index freshness guidance after reprocess/OCR, but leave rebuild execution user-triggered.

## Testing Decisions

- Unit tests should cover batch outcome classification and repository ownership checks.
- Integration tests should cover batch reprocess, OCR, and delete routes using deterministic fixtures and fake OCR providers.
- Frontend contract tests should cover row-click preview, checkbox selection, select-visible/clear-selection, toolbar state, action messages, partial-result rendering, and confirmation copy.
- Tests should assert external behavior and returned batch outcomes rather than parser/OCR internals.

## Further Notes

- This PRD should coordinate with PRD13 for OCR eligibility and warnings, and with PRD24 for future storage cleanup categories.
- If real batch OCR becomes slow enough to need progress updates, a later PRD can introduce jobs/progress without changing the selected-document and batch-result contract.
