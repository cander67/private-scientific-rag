# PRD 19: Repository Administration and Local Reset

**Status:** Backlog.

## Problem Statement

Researchers can now create, export, and recreate repositories across machines, but there is no first-class way to administer local repositories after repeated experiments. During PRD9 testing, a clean Windows machine could recreate a repository successfully, but resetting back to a clean local state still required manual deletion of database files, export artifacts, and derived indexes.

From a user's perspective, this is risky and unclear. They need a visible, deliberate way to list repositories, delete one repository, clear derived indexes, and reset local development state without guessing which files or directories are safe to remove.

## Solution

Add a repository administration workflow that lets users inspect local repositories and perform guarded cleanup actions from the app. The workflow should support deleting selected repositories, clearing all repositories, removing derived indexes, and documenting any remaining manual steps for external model caches or Docker-managed services.

The feature should make destructive actions explicit, preview the impact before execution, and report exactly what was deleted or preserved. It should treat source files, generated indexes, chat history, prompt sandbox history, exports, and local model caches as separate categories so users understand the blast radius.

## User Stories

1. As a researcher, I want to see all local repositories, so that I know what state exists on this machine.
2. As a researcher, I want repository rows to show names, creation dates, update dates, document counts, chat counts, and index status, so that I can choose what to keep.
3. As a researcher, I want to delete a selected repository, so that failed imports or experiments do not clutter my workspace.
4. As a researcher, I want deletion to remove repository-scoped documents, chunks, chat history, retrieval history, prompt sandbox history, and settings, so that the deleted repository is fully gone from the app.
5. As a researcher, I want repository deletion to remove derived full-text and vector index data for that repository, so that stale search data does not remain.
6. As a researcher, I want source files to be handled according to their storage category, so that app-managed copies can be deleted while externally referenced local files are preserved.
7. As a researcher, I want to preview a deletion summary before confirming, so that I can see the counts and storage categories affected.
8. As a researcher, I want destructive actions to require a clear confirmation, so that accidental clicks do not erase local work.
9. As a maintainer, I want reset actions to be repository-scoped by default, so that the app avoids broad machine cleanup unless explicitly requested.
10. As a maintainer, I want a "clear all repositories" workflow for local development and transfer testing, so that I can return the app to an empty state.
11. As a maintainer, I want clear-all to preserve external model caches by default, so that Ollama and SentenceTransformers downloads are not accidentally deleted.
12. As a maintainer, I want cleanup reports to list any files, directories, or indexes that could not be removed, so that failures are actionable.
13. As a Windows user, I want reset guidance and behavior that works with Windows-native paths, so that I do not need WSL-specific instructions.
14. As a macOS or Linux user, I want equivalent reset guidance and behavior, so that cross-platform transfer testing is consistent.
15. As a developer, I want an API-level administration surface, so that cleanup behavior can be tested independently from the UI.
16. As a developer, I want reset tests to use isolated temp directories and test databases, so that cleanup coverage is safe in CI.

## Implementation Decisions

- Add a repository administration view or section reachable from the existing app shell.
- Extend the repository list API to include repository summary counts and derived index status.
- Add a repository deletion preview endpoint that returns the records, app-managed files, derived indexes, and external references that would be affected.
- Add a guarded repository deletion endpoint that deletes one repository and its repository-scoped records.
- Add a guarded clear-all-local-repositories endpoint for local development and transfer testing.
- Treat model caches as out of scope for automatic deletion by default. The UI may explain where Ollama or SentenceTransformers caches usually live, but should not delete them unless a future PRD explicitly covers model management.
- Preserve externally mapped source files by default. Delete only app-managed source copies and generated artifacts that belong to the repository.
- Make Qdrant cleanup repository-aware. If Qdrant is unavailable during deletion, record that vector cleanup is incomplete and provide a retry path.
- Keep reset flows synchronous unless deletion proves too slow in real use. If long-running cleanup becomes necessary, defer persisted job orchestration to a later PRD.
- Require explicit user confirmation for destructive actions, including repository name confirmation or equivalent friction for clear-all.
- Record cleanup results in an audit-style response that the UI can display after the operation.

## Testing Decisions

- Tests should assert external behavior: preview counts, confirmed deletion results, preserved external files, removed app-managed files, removed database rows, and removed or reported vector indexes.
- Unit tests should cover cleanup planning logic, storage category classification, and confirmation validation.
- Integration tests should create multiple repositories in an isolated database, delete one repository, and verify the other repositories remain intact.
- Integration tests should verify clear-all removes all repository-scoped records and leaves the app able to recreate the default repository afterward.
- Integration tests should cover unavailable Qdrant cleanup reporting without making repository deletion appear fully successful.
- Frontend contract tests should cover repository administration visibility, preview-before-delete behavior, destructive confirmation copy, and cleanup result display.
- Cross-platform documentation should include Bash and PowerShell commands only as fallback/manual guidance; the app workflow should be the preferred path.

## Out of Scope

- Deleting Ollama model caches automatically.
- Deleting SentenceTransformers or Hugging Face caches automatically.
- Managing Docker installation, Docker Desktop settings, or system-wide Docker volumes beyond repository-scoped Qdrant cleanup.
- Cloud sync, multi-user permissions, or remote repository administration.
- Undo for destructive deletion.
- A general backup system beyond the existing PRD9 export bundle workflow.

## Further Notes

- PRD9 documentation currently includes manual clean-environment reset commands. This PRD should replace those instructions with a safer in-app workflow and leave manual commands as fallback guidance.
- Export should remain the recommended backup step before deletion.
- The implementation should be especially careful with Windows-native paths because PRD9 transfer testing now includes Windows machines without pre-existing repositories.
