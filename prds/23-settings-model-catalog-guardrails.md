# PRD 23: Settings Model Catalog and Collection Guardrails

**Status:** Ready for final review. Baseline catalog guardrails and all user-testing remediation phases are implemented with deterministic checks passing; optional live Ollama/Qdrant/GPU checks remain opt-in.

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

## Final Review Summary

PRD23 is ready for final review with the implementation plan fully checked off. The delivered scope includes:

- Catalog-backed Settings / Models choices for known embedding, chat, and reranker models, with detected/runtime entries separated from project-validated registry entries.
- Derived vector dimensions and compatible distance guardrails for known embedding models, while preserving explicit advanced/custom local model paths.
- Qdrant collection state and guidance that explain which workflow writes the vector collection, when rebuild is required, and where cleanup belongs.
- Expanded Ollama chat catalog guidance for current local workstation models while continuing to use the generic `/api/chat` provider.
- Ollama embedding readiness through the configured runtime, preferring `/api/embed`, falling back to legacy `/api/embeddings`, sending warm-up `keep_alive`, using startup-friendly timeouts, and marking readiness complete only after a vector with the expected dimension is returned.
- Load-aware Windows guidance that distinguishes unreachable runtime, missing pulled model, timeout/load-in-progress/load-failed responses, malformed responses, and vector-dimension mismatches.
- Chat Workspace visibility for the configured retrieval embedding model and latest vector-index model.
- Documentation for MiniLM device behavior, GPU/MPS/CUDA-to-CPU fallback, tokenizer choices, chunking modes, custom Ollama embedding models, and opt-in live checks.

Deterministic verification completed for the final review gate: formatting, linting, typing, backend tests, frontend contract tests, and frontend build. Live Ollama, Qdrant, SentenceTransformers cache, cross-encoder, and GPU checks are intentionally manual because they depend on local host/runtime state.

## User Testing Remediation

Hands-on testing after the baseline implementation surfaced several model and documentation gaps that remain inside PRD23 scope because they directly affect Settings / Models, model catalog guardrails, readiness checks, and model/runtime explanations.

### Additional User Stories

14. As a researcher, I want Settings / Models to include the local chat models I actually have installed, so that I can select them without typing model names from memory.
15. As a researcher, I want chat model guidance to clarify whether normal chat uses repository retrieval by default, so that I can trust the app is searching local context before asking the LLM.
16. As a Windows user, I want Ollama embedding readiness to check the configured Ollama runtime and model, so that a pulled model is not reported as unavailable without explaining which endpoint failed.
17. As a researcher, I want embedding readiness to cover both SentenceTransformers and Ollama providers, so that Settings / Models reflects the same providers vector rebuild can use.
18. As a researcher with a GPU-capable host, I want SentenceTransformers embedding checks and rebuilds to use GPU acceleration when available and safely fall back to CPU, so that larger local indexes can run faster without becoming GPU-required.
19. As a researcher, I want clear documentation for MiniLM device behavior, supported tokenizer choices, and chunking modes, so that model/runtime tradeoffs are understandable before changing settings.

### Additional Implementation Decisions

- Add `gemma4:e4b`, `gemma4:12b`, `qwen3.6`, and `qwen3.5:9b` to the known Ollama chat model catalog with setup guidance and resource/context notes. Treat them as ordinary Ollama `/api/chat` models unless future testing proves they need model-specific prompting.
- Keep chat retrieval defaults local and repository-grounded. Improve UI/docs copy rather than changing the default path: new chat sessions should continue to use chat-owned retrieval settings with hybrid retrieval by default.
- Extend Settings / Models readiness so Ollama embedding models are checked through the configured Ollama base URL and `/api/embed`, including vector-dimension validation against repository settings.
- Retry Ollama embedding readiness through the legacy `/api/embeddings` endpoint when a Windows or older local Ollama runtime cannot serve the current `/api/embed` endpoint, while keeping `/api/embed` as the preferred path.
- Treat Ollama embedding readiness as a warm-up request by sending `keep_alive` and using startup-friendly timeouts. Installed model files still have to be loaded into memory on first use, and large models can fail on Windows when the runtime cannot allocate enough RAM/VRAM.
- Deem Ollama embedding readiness complete only after the runtime returns a vector with the expected dimension. If Ollama lists the model locally but the embedding endpoint times out or returns no vector, report an installed-but-not-loaded/load-failed state instead of not installed.
- Distinguish unavailable Ollama runtime, missing model, failed embedding response, and dimension mismatch in readiness messages.
- Add a SentenceTransformers device policy for embeddings and reranker-adjacent docs: prefer GPU/MPS/CUDA when available and configured for automatic acceleration, then fall back to CPU when no supported accelerator is available or when an accelerator load fails safely.
- Do not make GPU a required dependency for default CI or local setup. Default tests should continue to mock live model/runtime boundaries.
- Document current tokenizer support (`unicode61`, `porter`) and explicitly defer broader tokenizer expansion until retrieval-quality evidence or corpus needs justify it.
