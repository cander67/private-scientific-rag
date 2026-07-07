# PRD 16: Immutable Embedding Indexes

## Goal

Allow researchers to preserve, compare, export, and reuse multiple embedding indexes for the same repository instead of replacing the latest vector index on every rebuild.

## User Stories

- As a researcher, I can create a new immutable embedding index before changing embedding settings, so that old search behavior remains reproducible.
- As a researcher, I can choose which embedding index to search, so that I can compare retrieval behavior across models or settings.
- As a maintainer, I can clean up unused embedding indexes and Qdrant collections, so that local storage remains manageable.
- As a researcher, I can export index metadata and settings so an old vector index can be recreated on another machine.

## Scope

- Add user-visible immutable embedding run/index records.
- Preserve one Qdrant collection per immutable embedding run.
- Let vector search target a selected embedding run, with latest run as the default.
- Add list, inspect, activate, and delete/archive operations for embedding indexes.
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
- Search Lab can select between available embedding indexes.

## Test Plan

- Unit tests for immutable index lifecycle rules.
- Integration tests creating two indexes for one repository and searching each independently.
- Qdrant cleanup tests for deleted/archive indexes.
- Export/recreate validation tests for selected embedding index metadata.

## Notes

PRD5 keeps only one latest vector index per repository to reduce local storage and complexity. This PRD should be implemented when users need repeatable comparison across models, settings, or historical runs.
