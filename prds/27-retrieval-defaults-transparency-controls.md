# PRD 27: Retrieval Defaults Transparency and Controls

**Status:** Backlog.

## Problem Statement

PRD6, PRD7, PRD8, PRD21, and PRD23 delivered unified retrieval, Search Lab, Chat Workspace, Prompt Sandbox, settings, and model guardrails. In hands-on use, the retrieval controls still feel inconsistent across workflows.

Search Lab exposes candidate pool size, RRF constant, metadata boost levels, metadata filters, and reranker strategy. Chat Workspace and Prompt Sandbox use narrower chat-style retrieval settings. Some defaults are hard-coded in frontend state, some live in Pydantic schemas, some are derived in services, and some are implied by repository settings impact analysis without being editable or visible in one place.

Metadata boosting is also not transparent enough. Users can avoid metadata boosting by selecting a non-boost reranker strategy, but once a metadata-boost strategy is selected the boost levels can only be low, medium, or high. There is no explicit `off` value for individual boost dimensions, and the UI does not clearly explain when metadata boosts are applied to ranking versus merely displayed as metadata.

## Solution

Create a single visible retrieval-defaults contract for the app. The contract should document and expose the defaults used by Search Lab, Chat Workspace, Prompt Sandbox, retrieval evaluation, and future promotion flows. It should preserve workflow-specific overrides, but make the source of every default clear to the user.

Add an explicit `off` state for metadata boost dimensions. Users should be able to run metadata-boost strategies while disabling one or more boost dimensions, and the result score breakdown should show that disabled dimensions contributed zero. The UI should also distinguish "metadata shown on a result" from "metadata used to boost ranking."

This PRD addresses shortcomings in completed PRDs rather than reopening them: PRD6 owns the original retrieval implementation, PRD7 owns the original chat integration, PRD8 owns sandbox experiments, PRD21 owns the first settings surface, PRD23 owns model/catalog guardrails, PRD18 owns evidence-backed promotion, and PRD25 owns chat context inspection.

## User Stories

1. As a researcher, I want to see the effective retrieval defaults for Search Lab, Chat Workspace, Prompt Sandbox, and evaluation, so that I know why the same query may behave differently across workflows.
2. As a researcher, I want to control metadata boosting with an explicit `off` option, so that metadata can be displayed without affecting rank.
3. As a researcher, I want candidate pool, RRF constant, reranker strategy, metadata boosts, filters, and final top-k to be visible when they affect chat context, so that chat behavior is not mysterious.
4. As a researcher, I want Search Lab changes to remain experimental unless I explicitly copy or promote them, so that ad hoc search tuning does not silently alter chat.
5. As a researcher, I want new chat sessions to start from repository chat retrieval defaults, so that normal chat reflects my chosen defaults.
6. As a researcher, I want existing chat sessions to preserve their saved retrieval settings, so that old answers remain reproducible after defaults change.
7. As a researcher, I want Prompt Sandbox and evaluation runs to show whether they are using repository defaults or per-run overrides, so that comparisons are interpretable.
8. As a maintainer, I want one schema for retrieval defaults and one normalization path for older saved settings, so that defaults do not drift across services.
9. As a maintainer, I want retrieval runs to keep recording the exact effective settings, so that exports, recreate, and audits remain reliable.
10. As a maintainer, I want deterministic tests for default resolution, metadata boost off behavior, and workflow override precedence.

## Scope

- A repository-scoped retrieval defaults model that can represent chat defaults and optionally reusable Search Lab/Sandbox presets.
- Explicit effective-settings resolution for each workflow: repository defaults, session defaults, per-run overrides, and hard fallback defaults.
- Metadata boost levels extended from low/medium/high to include `off`.
- Metadata boost scoring updated so each disabled dimension contributes zero and is visible in score breakdown metadata.
- Chat retrieval settings expanded to include candidate pool size, RRF constant, metadata boost settings, and metadata filters where useful for normal chat.
- Settings / Models retrieval section that shows defaults, source, and impact without becoming an experiment manager.
- Search Lab copy/promote actions that can move a retrieval configuration into a chat session or repository defaults through explicit user action.
- Prompt Sandbox and evaluation display of effective retrieval settings and whether values came from defaults or overrides.
- Export/recreate compatibility for the new retrieval defaults and old saved sessions.
- Documentation and tests that describe default precedence and metadata boost semantics.

## Non-Goals

- Automatic promotion of retrieval defaults based on ad hoc search results.
- Replacing PRD18 evidence-backed promotion.
- Replacing PRD25 chat context inspection.
- New ranking algorithms beyond making existing metadata boosts configurable and transparent.
- Full metadata quality/scoping fixes owned by PRD17.
- Multi-user permissions for who can promote defaults.

## Acceptance Criteria

- Repository settings can store retrieval defaults that include mode, top-k, candidate pool size, RRF constant, reranker strategy, metadata boost dimensions, and optional metadata filters.
- Metadata boost dimensions support `off`, `low`, `medium`, and `high`.
- When a metadata boost dimension is `off`, it contributes zero to ranking and is represented clearly in score breakdown or effective-settings output.
- Search Lab still supports per-run overrides and does not mutate chat or repository defaults unless the user chooses an explicit copy/promote action.
- New chat sessions start from repository chat retrieval defaults.
- Existing chat sessions with older settings normalize safely and preserve their effective historical behavior where possible.
- Chat questions pass the complete effective retrieval settings into unified retrieval.
- Prompt Sandbox and retrieval evaluation show the effective retrieval settings used for every run.
- Settings / Models makes retrieval-default sources and workflow differences visible.
- Export/recreate preserves retrieval defaults and remains backward-compatible with old bundles.
- Tests cover default resolution, metadata boost off behavior, Search Lab non-mutation, copy/promote behavior, chat session inheritance, old-session normalization, and retrieval-run snapshots.

## Implementation Decisions

- Keep the unified retrieval endpoint as the execution path. This PRD should change settings/default resolution and UI transparency, not fork retrieval.
- Treat metadata boost display and metadata boost ranking as separate concepts in UI copy and score breakdowns.
- Prefer a shared Pydantic model for retrieval defaults, with workflow-specific wrappers only where the workflow truly needs a smaller surface.
- Preserve explicit workflow overrides: Search Lab, Chat Workspace, and Prompt Sandbox can still run different settings for experimentation.
- Keep PRD18 as the governance layer for evidence-backed default promotion; this PRD may add manual copy/promote plumbing, but it should not require golden evidence for every local change.
- Keep old persisted chat/session/sandbox payloads readable through normalization rather than migration-only assumptions.

## Testing Decisions

- Unit tests should cover default resolution precedence and metadata boost scoring with `off`.
- Integration tests should verify chat, Search Lab, Prompt Sandbox, and evaluation run requests persist effective settings.
- Integration tests should verify old saved chat settings load with deterministic normalized defaults.
- API tests should verify Search Lab copy/promote changes only the requested target.
- Frontend contract tests should cover Settings / Models retrieval defaults, Search Lab copy/promote affordances, Chat Workspace advanced retrieval settings, metadata boost off controls, and effective-settings labels.
- Export/recreate tests should cover bundles with and without the new retrieval defaults.

## Further Notes

- PRD17 should still fix whether metadata labels are trustworthy and scoped correctly. This PRD assumes the available metadata may be imperfect but gives users control over whether it affects ranking.
- PRD25 should use the effective-settings resolver so chat context inspection matches actual chat execution.
- PRD18 promotion can later add evidence requirements on top of the explicit copy/promote path introduced here.
