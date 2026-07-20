# PRD 26: Repository Loading and Parser Controls

**Status:** Ready for review.

## Problem Statement

User testing found two places where the app feels less controlled than the underlying system actually is. First, when switching repositories, the dashboard and workspace data can take time to reload without a clear repository-loading status. Second, Settings / Models currently exposes structured parser and fallback parser as free-text fields even though researchers usually need a safe list of supported choices.

These issues create avoidable uncertainty: users cannot tell whether the selected repository state is still loading, and parser settings look like arbitrary strings instead of reproducible local configuration.

## Solution

Add explicit repository-switch loading states across the dashboard and app shell, and replace parser free-text defaults with fixed parser choices plus an `Auto` option and an advanced custom path where appropriate.

The repository loading work should make state transitions visible without adding a background job system. The parser controls should remain repository-scoped settings and continue to participate in existing impact analysis, validation, snapshots, export/recreate manifests, and reprocessing guidance.

## User Stories

1. As a researcher, I want visible status when changing repositories, so that I know the app is loading the selected repository state.
2. As a researcher, I want dashboard status to distinguish loading, loaded, failed, and empty repository states, so that stale data is not mistaken for current data.
3. As a researcher, I want workspace views to avoid showing the previous repository as current while the new repository is loading, so that I do not act on stale context.
4. As a researcher, I want parser settings to offer fixed choices, so that I can configure ingestion without memorizing parser IDs.
5. As a researcher, I want an `Auto` parser option, so that the app can use its best default chain while future parser-selection logic remains possible.
6. As a researcher, I want fallback parser choices to be explicit, so that failure behavior is reproducible.
7. As a researcher, I want parser changes to keep showing document reprocessing impact, so that old chunks are not silently treated as refreshed.
8. As a Windows user, I want parser guidance to avoid Unix-only setup assumptions, so that local configuration is understandable on Windows-native Python.
9. As a maintainer, I want parser choices validated by the backend as well as constrained by the UI, so that imported manifests and API clients cannot save unsupported values silently.

## Implementation Decisions

- Track repository activation as an explicit loading lifecycle in the frontend shell.
- Clear or mark repository-scoped summaries as loading when the active repository changes.
- Show repository-loading status in Repository Dashboard and the app subtitle/header while counts, settings, model catalog, documents, chats, and summaries refresh.
- Preserve existing route structure and repository selector behavior.
- Introduce canonical parser choice metadata that Settings / Models can render as select controls.
- Include `Auto`, known structured parsers, known fallback parsers, and an advanced custom path only if backend validation supports it.
- Keep parser settings in repository settings and existing export/recreate manifests.
- Keep existing settings impact behavior for parser changes: document reprocessing and downstream rebuild warnings remain required.

## Testing Decisions

- Frontend contract tests should verify repository-switch loading states, stale-data avoidance, and dashboard loading/error/empty state labels.
- Unit or integration tests should verify parser setting validation accepts known choices and rejects unsupported values unless advanced custom mode is intentionally allowed.
- Integration tests should verify parser changes still appear in settings impact analysis and manifests.
- Frontend contract tests should verify structured parser and fallback parser controls render fixed options, `Auto`, and validation messaging.

## Out of Scope

- Background job orchestration for repository loading.
- Parser quality improvements, OCR, table extraction, or structured multimodal parsing.
- Reprocessing documents automatically after parser changes.
- Bulk parser plugin management.

## Further Notes

- This PRD combines user-testing feedback about repository loading status and parser controls because both improve confidence in repository-scoped state.
- Future parser-selection logic can define what `Auto` means in more depth without changing the user-facing setting shape.
- Implementation keeps `Auto` as the default structured and fallback parser setting. The catalog exposes current parser packages plus backlog parser choices from PRD13/PRD14: PyMuPDF, Docling, pdfplumber, pypdf, built-in fallback, the `needs_ocr` gate, OCRmyPDF/Tesseract, and RapidOCR.
- OCR choices are selectable as repository-scoped fallback metadata, but PRD26 does not run OCR automatically. OCR execution, confidence handling, and dependency checks remain PRD13 scope.
- Parser choices are validated, saved, exported/recreated, shown in Settings / Models, and included in impact analysis, but upload/reprocess execution still uses the existing ingestion parser chain until PRD13 wires operational parser routing.
- Advanced arbitrary parser paths were intentionally not added because backend validation now rejects unsupported parser IDs; adding custom parser adapters should come with a validated adapter contract.
- Verification for this branch: `uv run ruff format .`, `uv run ruff check . --fix`, `uv run mypy src tests`, `uv run pytest`, `npm test`, and `npm run build` passed locally.
