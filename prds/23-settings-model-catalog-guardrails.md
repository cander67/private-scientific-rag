# PRD 23: Settings Model Catalog and Collection Guardrails

**Status:** Backlog.

## Problem Statement

User testing showed that Settings / Models still asks users to type model names and embedding dimensions even though the app already knows several supported embedding models and validates compatibility after the fact. This leaves users copying names from docs, guessing dimensions, and discovering mistakes only when save or rebuild validation fails.

The same page exposes a Qdrant collection name, but it does not make the downstream role of that collection obvious. Users cannot tell whether the field changes search behavior, creates a new collection, replaces an old collection, or requires a manual backend task.

## Solution

Add a model catalog and settings guardrail layer to Settings / Models. The UI should present known chat, embedding, and reranker options as selectable choices, derive embedding dimensions from selected model metadata when possible, constrain incompatible distance/dimension combinations before save, and preserve an explicit advanced/custom path for local models that are not in the registry.

The page should also explain the Qdrant collection lifecycle in the setting itself: the collection is used by vector rebuild/search for the repository's active vector index, collection changes require a vector rebuild before search uses them, and collection cleanup is handled through repository administration or future immutable index management rather than manual filesystem deletion.

## User Stories

1. As a researcher, I want to choose a chat model from detected or known local model options, so that I do not need to type model names from memory.
2. As a researcher, I want to choose an embedding provider and model from supported options, so that I avoid invalid provider/model combinations.
3. As a researcher, I want embedding dimensions to auto-fill from the selected model, so that I do not accidentally save a mismatched vector size.
4. As a researcher, I want incompatible embedding dimensions and distances to be disabled or clearly marked, so that invalid settings are caught before save.
5. As a researcher, I want to see the default dimension for each known embedding model, so that I understand why a setting changed.
6. As a researcher, I want an advanced/custom model entry path, so that I can still use local models that are not yet in the app registry.
7. As a researcher, I want custom embedding models to require a dimension probe or explicit compatibility warning, so that experimental models do not silently corrupt vector settings.
8. As a researcher, I want to understand what the Qdrant collection setting controls, so that I know when a vector rebuild is required.
9. As a researcher, I want Qdrant collection names to show active, stale, missing, or not-yet-created state where known, so that settings do not feel disconnected from search.
10. As a researcher, I want links from collection warnings to the exact workflow that can rebuild or clean up vectors, so that I do not need manual backend knowledge.
11. As a maintainer, I want one canonical model catalog API, so that frontend dropdowns, validation, documentation, and readiness checks share the same metadata.
12. As a maintainer, I want the catalog to separate known registry entries from detected local runtime entries, so that the app can be helpful without claiming every local model is validated.
13. As a maintainer, I want default CI to mock live model detection, so that catalog tests remain deterministic.

## Implementation Decisions

- Add a repository-scoped or app-scoped model catalog endpoint that returns known chat, embedding, and reranker options plus compatibility metadata.
- Use the existing embedding model registry as the canonical source for known embedding provider/model, vector size, supported distance, resource notes, setup hints, and local-model requirements.
- Add a small chat model catalog that can include project-known defaults and optionally detected Ollama models from a user-triggered runtime check.
- Keep custom model entry available behind an advanced/manual mode. Known models should be selectable; unknown models should be explicit and carry validation/probe requirements.
- Treat embedding vector size as derived and locked for known models. If the UI shows the value, it should be read-only or selectable only among compatible values.
- Disable or mark unsupported distance choices for known embedding models instead of letting users save and later discover the error.
- Preserve backend validation as the final authority. UI guardrails improve the experience but do not replace API validation.
- Show Qdrant collection usage beside the field: the setting controls the repository vector index collection used by rebuild/search, and changing it does not migrate vectors until rebuild.
- Add collection state where available from existing embedding run records and Qdrant readiness checks: active, stale, missing, unreachable, or not checked.
- Link vector-impact warnings to Search Lab/vector rebuild and cleanup warnings to Repository Administration.
- Do not implement full multi-index selection here. PRD16 remains the owner for retaining, selecting, comparing, and deleting multiple immutable embedding indexes.

## Testing Decisions

- Unit tests should cover catalog construction, embedding compatibility metadata, and known/custom model classification.
- Integration tests should verify the model catalog endpoint returns known embedding models with dimensions and supported distances.
- Integration tests should verify unknown custom embedding models still require backend validation or a live dimension probe before rebuild.
- Frontend contract tests should cover model dropdown rendering, custom-entry mode, dimension auto-fill/read-only behavior, disabled incompatible choices, and Qdrant collection explanatory state.
- Live Ollama model discovery should be opt-in and mocked by default.

## Out of Scope

- Automatic model download, install, or deletion.
- Cloud-hosted model provider configuration.
- Automatic model quality recommendations or benchmark-based promotion.
- Managing multiple active embedding indexes or selecting historical indexes.
- Deleting Qdrant collections directly from Settings / Models.

## Further Notes

- This PRD is a user-testing follow-up to PRD15 and PRD21. Those PRDs built the registry, validation, and Settings / Models page; this PRD makes those capabilities harder to misuse.
- Qdrant collection management should be explained here but administered through Repository Administration and PRD16's future immutable index lifecycle.
