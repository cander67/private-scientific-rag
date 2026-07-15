# PRD 21: Settings and Model Manager

**Status:** Ready for review.

## Problem Statement

The app already has repository settings, prompt-library settings, model defaults, retrieval settings, export settings, and model readiness checks spread across backend services and workflow-specific pages. The sidebar also includes a Settings / Models placeholder, but there is no implemented page where a user can inspect and manage repository defaults in one place.

This creates friction for users who need to understand or change chunking, full-text, vector, reranking, chat, prompt, and export defaults. It also makes model setup harder to diagnose because chat, embedding, and reranker readiness are checked from different contexts.

## Solution

Build a Settings / Model Manager page for repository-scoped defaults and local model readiness. The page should let users inspect and update repository settings, validate local model availability, smoke-test configured services, and understand when a settings change requires reprocessing, full-text rebuild, vector rebuild, or recreated exports.

The page should use the existing repository settings API foundation from the reproducibility work, while filling in the missing product UI and any API gaps needed for safe editing, validation, and readiness reporting.

## User Stories

1. As a researcher, I want a Settings / Models page, so that the sidebar destination is real and navigable.
2. As a researcher, I want to see settings for the active repository, so that defaults are clearly repository-scoped.
3. As a researcher, I want to edit chunking mode, chunk size, and overlap, so that future parsing can match my corpus needs.
4. As a researcher, I want to edit parser and fallback parser settings, so that document ingestion behavior is reproducible.
5. As a researcher, I want to edit full-text search settings such as field weights and tokenizer choices where supported, so that sparse retrieval can be tuned.
6. As a researcher, I want to edit vector settings such as embedding provider, embedding model, distance metric, and Qdrant collection policy, so that semantic retrieval can be configured deliberately.
7. As a researcher, I want to edit reranking defaults, candidate-pool defaults, metadata boost defaults, and final top-k defaults, so that retrieval behavior is understandable before chat or sandbox runs.
8. As a researcher, I want to edit chat model defaults and context defaults, so that Chat Workspace starts from the intended local model configuration.
9. As a researcher, I want to manage repository chat prompt library entries, so that default chat behavior is visible and reproducible.
10. As a researcher, I want to choose the active chat prompt from the prompt library, so that normal chat defaults are explicit.
11. As a researcher, I want to see export defaults, so that portable bundles include the expected settings and source-file behavior.
12. As a researcher, I want to validate settings before saving, so that invalid model names, dimensions, or unsupported combinations are caught early.
13. As a researcher, I want to know which settings changes require reprocessing documents, rebuilding full-text, rebuilding vectors, or rerunning evaluations, so that changes do not silently make indexes stale.
14. As a researcher, I want to test Qdrant connectivity, so that vector issues are diagnosed from settings.
15. As a researcher, I want to test the configured chat model through Ollama, so that chat readiness is clear before I ask a question.
16. As a researcher, I want to check embedding and cross-encoder model availability, so that missing local model caches are visible.
17. As a Windows user, I want model and service guidance to avoid assuming Bash paths or Linux service behavior, so that Windows-native setup is supported.
18. As a maintainer, I want settings saves to create reproducibility snapshots where appropriate, so that changed defaults can be audited.
19. As a maintainer, I want settings APIs to preserve backward-compatible manifests and exports, so that PRD9 recreate remains reliable.
20. As a maintainer, I want model readiness checks to be explicit and opt-in where they may touch local model runtimes, so that loading large local models is not surprising.
21. As a maintainer, I want the Settings / Models page to avoid becoming an experiment manager, so that prompt comparisons and evaluation evidence remain in their own workflows.

## Implementation Decisions

- Add a first-class Settings / Models frontend view and make the existing sidebar item navigable.
- Use repository-scoped settings as the source of truth. Do not introduce global settings unless a specific setting truly applies outside a repository.
- Organize the UI into focused sections or tabs: chunking/parser, full-text, vector, reranking, chat/LLM, prompts, export defaults, and model registry/readiness.
- Reuse existing repository settings schemas and update endpoints where possible.
- Add validation APIs or extend existing validation so the UI can show field-level errors before saving.
- Add settings impact analysis that identifies whether a change affects parsing, full-text index, vector index, chat defaults, prompt defaults, export defaults, or recreate compatibility.
- Preserve current workflow-owned controls. Search Lab can still override retrieval settings for a search, Chat Workspace can still use chat-owned retrieval controls, and Prompt Sandbox can still run isolated prompt/retrieval/model comparisons.
- Add model registry/readiness summaries for configured chat, embedding, and reranking models. Checks should distinguish not checked, unavailable runtime, not installed, installed/ready, and failed smoke test.
- Treat model download/install automation as optional and conservative. If implemented, it should be explicit, user-triggered, and documented per runtime. The first implementation may show commands/guidance rather than performing downloads.
- Keep settings changes synchronous unless future model or service checks require a persisted job system.
- Use the existing settings-model-manager mockup as visual guidance, but align with current React/Vite app structure and shipped design patterns.

## Testing Decisions

- Tests should assert external behavior: settings load, validation feedback, successful save, impact warnings, model readiness display, and navigation.
- Unit tests should cover settings validation and impact-analysis logic.
- Integration tests should verify repository settings round-trip through API requests.
- Integration tests should verify invalid settings are rejected with actionable errors.
- Integration tests should verify settings changes remain repository-scoped and do not affect other repositories.
- Integration tests should verify manifest/export output reflects saved settings.
- Tests should verify settings that affect indexes mark the relevant readiness or index state as stale where the system supports staleness detection.
- Frontend contract tests should cover tab/section visibility, save/cancel behavior, field-level validation, model readiness labels, and links back to affected workflows.
- Live model checks should remain opt-in and documented; default CI should mock Ollama, SentenceTransformers, cross-encoder, and Qdrant readiness boundaries.

## Out of Scope

- Repository deletion, reset, or destructive administration workflows.
- Golden evaluation, promotion evidence, or maintainer scoring workflows.
- Automatic model selection based on quality benchmarks.
- Bulk model download management across all possible local runtimes.
- Cloud model provider configuration.
- Multi-user permissions or shared repository administration.
- Replacing workflow-specific controls in Search Lab, Chat Workspace, Prompt Sandbox, Export Center, or Recreate Repository.

## Further Notes

- PRD2 created the repository settings and reproducibility foundation. This PRD completes the missing product surface for viewing, editing, validating, and explaining those settings.
- The page should make settings safe to change by clearly showing what must be rebuilt or revisited after a save.
- Export/recreate compatibility should remain a central design constraint because settings are part of portable repository bundles.
