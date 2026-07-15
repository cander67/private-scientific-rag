# PRD 9: Export, Import, and Recreate Repository

**Status:** Complete and closed.

## Goal

Export complete research bundles and recreate repositories from settings, manifests, source files, and local models across supported operating systems.

## User Stories

- As a researcher, I can export a chat, settings, prompts, retrieval runs, chunks, citations, and source files as a ZIP.
- As a researcher, I can recreate a repository from an exported bundle.
- As a researcher, I can see clear warnings for missing files, missing models, parser mismatches, or changed chunk counts.

## Scope

- ZIP export service.
- Manifest export.
- Settings export.
- Source/chunk/citation export.
- Import/recreate validation.
- Rebuild full-text and vector indexes.
- Export Center UI.
- Recreate Repository UI.
- Cross-platform transfer docs.

## Implementation Decisions

- Recreate should prefer creating a new repository from an exported bundle, while also supporting restore into an existing empty repository.
- Exported chat and retrieval history should be restored as active records so the recreated repository can build on prior work.
- Bundles that exclude source files should support mapping external local files by deterministic SHA-256 hash and path, and recreate should report any missing or mismatched files clearly.
- PRD8 sandbox runs and comparisons should not be included by default; they can be included through an explicit export option.
- The first implementation should use progress-friendly synchronous export/recreate flows instead of persisted long-running jobs.

## Acceptance Criteria

- Export ZIP includes manifest, settings, repository snapshot, prompts, retrieval runs, chunks, citations, and selected sources.
- Recreate validates source hashes before rebuild.
- Recreate rebuilds SQLite FTS5 and Qdrant indexes.
- Recreate report flags missing models, source hash mismatches, parser changes, and index differences.
- Export created on one supported OS can be validated on another supported OS.

## Test Plan

- Unit test manifest validation.
- Integration test export ZIP structure.
- Integration test recreate from exported settings and source files.
- Cross-platform validation checklist for macOS, Windows, and Linux/Ubuntu.

## Documentation References

- `docs/public_repo_checklist.md` for public-safe exported examples.
- `docs/export_recreate.md` for bundle contents, recreate workflow, warning meanings, and cross-platform transfer checklist.
- Python `zipfile` documentation: https://docs.python.org/3/library/zipfile.html
- Qdrant documentation: https://qdrant.tech/documentation/overview/
- SQLite FTS5 documentation: https://www.sqlite.org/fts5.html
