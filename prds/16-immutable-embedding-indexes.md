# PRD 16: Immutable Embedding Indexes

## Goal

Allow researchers to preserve, compare, export, and reuse multiple embedding indexes for the same repository instead of replacing the latest vector index on every rebuild.

## User Stories

- As a researcher, I can create a new immutable embedding index before changing embedding settings, so that old search behavior remains reproducible.
- As a researcher, I can choose which embedding index to search, so that I can compare retrieval behavior across models or settings.
- As a maintainer, I can clean up unused embedding indexes and Qdrant collections, so that local storage remains manageable.
- As a researcher, I can export index metadata and settings so an old vector index can be recreated on another machine.
- As a researcher, I can see which Qdrant collection belongs to each embedding index, so that collection names in settings and `.qdrant/collections` are understandable.
- As a researcher, I can tell whether an index collection is active, archived, missing, stale, or orphaned, so that I do not need manual backend inspection.

## Scope

- Add user-visible immutable embedding run/index records.
- Preserve one Qdrant collection per immutable embedding run.
- Let vector search target a selected embedding run, with latest run as the default.
- Add list, inspect, activate, and delete/archive operations for embedding indexes.
- Show each embedding index's Qdrant collection name, model, vector size, distance, created time, active/archive state, and storage/cleanup status.
- Detect Qdrant collections that no longer map cleanly to an embedding run and report them as cleanup candidates.
- Include immutable embedding index metadata in repository export/recreate flows.
- Extend Search Lab to display and select an embedding index.

## Out Of Scope

- Sharing actual Qdrant vector data in portable exports by default.
- Automatic model benchmarking or index recommendation.
- Hybrid search index selection beyond passing the selected vector index into PRD6 workflows.

## Acceptance Criteria

- A rebuild can either replace the latest index or create a new immutable embedding index, depending on user choice.
- Search can target a specific embedding run/index and reports that selection in every result.
- Repository export includes embedding index settings and recreate instructions.
- Deleting or archiving an index removes or disables the matching Qdrant collection without affecting documents or full-text search.
- Index inspection maps Qdrant collections back to embedding runs and flags missing or orphaned collections with clear cleanup guidance.
- Search Lab can select between available embedding indexes.

## Test Plan

- Unit tests for immutable index lifecycle rules.
- Integration tests creating two indexes for one repository and searching each independently.
- Qdrant cleanup tests for deleted/archive indexes.
- Export/recreate validation tests for selected embedding index metadata.

## Notes

PRD5 keeps only one latest vector index per repository to reduce local storage and complexity. This PRD should be implemented when users need repeatable comparison across models, settings, or historical runs.
