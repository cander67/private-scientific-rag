# PRD 32: Workflow Friction Remediation

**Status:** Ready for final review. Not complete until user acceptance.

## Problem Statement

User testing found several small but compounding workflow frictions after Settings / Models, Search Lab, Chat Workspace, and Document Manager became fully usable.

Settings / Models can require long scrolling after a user changes lower-page model, parser, OCR, retrieval, prompt, or export defaults because the primary save controls live at the top of the page. Search Lab and Chat Workspace correctly report stale parser or chunk settings when indexes no longer match current repository settings, but they do not give users a direct path to refresh the repository from the same place where the stale state is discovered. Chat Workspace persists chat sessions, but default names are repetitive and there is no edit path for a user to name or rename a conversation.

These issues do not require changing the core retrieval, parser, or chat model architecture. They require better recovery actions and small UI/API affordances at the points where users already are.

## Solution

Add low-risk remediation affordances across the existing workflow surfaces:

- Mirror Settings / Models save and cancel controls at the bottom of the settings page, using the same dirty, validation, impact, and busy state as the top controls.
- When Search Lab or Chat Workspace encounters stale parser/chunk settings while rebuilding or querying, surface a direct repository reprocess action from that workflow. After reprocess completes, users can trigger the existing full-text/vector rebuild controls without navigating to Document Manager first.
- Keep Document Manager as the owner of full repository reprocess implementation details through PRD28, and reuse that API from Search Lab and Chat Workspace.
- Add chat-session rename support so users can name and edit chat titles without losing existing session history or retrieval settings.

## User Stories

1. As a researcher, I can save Settings / Models changes from the bottom of the page, so that I do not have to scroll back to the top after editing lower sections.
2. As a researcher, I can cancel lower-page settings edits from the bottom of the page, so that the bottom controls mirror the top workflow.
3. As a researcher, when Search Lab finds stale parser or chunk settings, I can reprocess the repository from Search Lab before rebuilding indexes.
4. As a researcher, when Chat Workspace finds stale parser or chunk settings, I can reprocess the repository from Chat Workspace before rebuilding indexes.
5. As a researcher, after repository reprocess completes from Search Lab or Chat Workspace, readiness, dashboard, document, and index status refresh so I know the next rebuild step.
6. As a researcher, I can rename a chat session, so that multiple conversations are distinguishable.
7. As a researcher, new chat sessions use a less repetitive default title, so that the chat list remains usable even before I rename anything.
8. As a maintainer, I want stale-repair actions to reuse the Document Manager batch reprocess API, so that reprocess behavior is consistent across workflows.
9. As a maintainer, I want chat rename to update only the selected session title, so that messages, retrieval settings, prompt ID, model, and reproducibility state remain intact.
10. As a maintainer, I want deterministic frontend and backend tests for these affordances, so that future polish does not regress the recovery workflow.

## Scope

- Bottom Settings / Models save/cancel control row.
- Shared settings-save state and validation behavior between top and bottom save controls.
- Stale parser/chunk error detection in Search Lab and Chat Workspace user messages.
- Search Lab repository reprocess action that calls the PRD28 full-repository reprocess route/request mode.
- Chat Workspace repository reprocess action that calls the same PRD28 full-repository reprocess route/request mode.
- Refresh of documents, chat readiness, dashboard summary, and relevant workflow messages after cross-workflow repository reprocess.
- Chat-session rename API and UI.
- Better new-chat default title behavior, such as timestamped default titles or title generation from the first user question if it can be implemented deterministically and locally.
- Tests for settings bottom save, stale repair calls, state refresh, and chat rename.

## Non-Goals

- Replacing PRD28's Document Manager row preview, selected batch actions, or full-repository reprocess implementation.
- Automatically rebuilding full-text or vector indexes after reprocess.
- Creating a background job queue for reprocess/rebuild progress.
- Automatically reprocessing immediately after settings save.
- Renaming historical messages, retrieval runs, exports, or prompt records.
- AI-generated chat title summarization through a local LLM.
- Changing retrieval ranking, parser routing, OCR behavior, or model-readiness semantics.

## Acceptance Criteria

- Settings / Models renders bottom save and cancel controls after the final settings section.
- Bottom save uses the same validation, disabled, busy, dirty, impact, and success/error behavior as the top save control.
- Bottom cancel resets the same draft state as the top cancel control.
- Search Lab detects stale parser/chunk rebuild or search failures and shows a direct reprocess-repository action.
- Chat Workspace detects stale parser/chunk readiness, rebuild, context-preview, or ask failures and shows a direct reprocess-repository action.
- Cross-workflow reprocess calls the PRD28 full-repository reprocess contract and reports completed, skipped, failed, and missing-source counts.
- After cross-workflow reprocess, documents, dashboard summary, chat readiness, and current workflow status refresh.
- Full-text and vector rebuild remain explicit user-triggered actions after reprocess.
- Chat sessions can be renamed through a repository-scoped API.
- Chat rename validates non-empty titles and preserves messages, retrieval settings, model, prompt ID, and repository ownership.
- The chat session list updates the renamed title without requiring a browser refresh.
- New chat sessions avoid indistinguishable repeated titles.
- Tests cover bottom settings save/cancel, stale repair CTA behavior, successful and partial reprocess summaries from Search Lab and Chat Workspace, chat rename API behavior, and chat rename UI behavior.

## Implementation Decisions

- Keep Settings / Models as one repository-scoped settings editor. The bottom save/cancel controls should call the same handlers as the top controls rather than introducing separate state.
- Treat parser/chunk staleness as a recoverable workflow state, not a generic search/chat failure. Existing error text can be parsed conservatively at first, but backend error details may be structured if needed for reliable UI behavior.
- Reuse PRD28's full-repository reprocess route/request mode. Search Lab and Chat Workspace should not duplicate document iteration logic.
- Reprocess from Search Lab and Chat Workspace should refresh app state but should not silently rebuild indexes. The user still chooses full-text, vector, or hybrid rebuild after document chunks are current.
- Add a chat-session update contract that accepts `title` only for now. Future session updates can extend the schema if needed, but this PRD should not make retrieval settings editable through the rename endpoint.
- Prefer deterministic default chat names. If first-message title generation is added, derive it locally from the first question text with length limits instead of calling an LLM.

## Testing Decisions

- Frontend contract tests should cover bottom save/cancel controls in Settings / Models using existing settings fixtures.
- Frontend contract tests should simulate stale Search Lab and Chat Workspace failures and verify the reprocess action, status copy, and refresh behavior.
- Backend integration tests should cover chat-session rename success, empty title rejection, missing session, and wrong-repository protection.
- Integration or frontend contract tests should verify renamed chat sessions remain selectable and retain messages.
- Cross-workflow reprocess tests should mock or fixture the PRD28 batch response shape rather than depending on OCR, Qdrant, Ollama, or external model runtimes.
- Default CI should remain deterministic. Optional live checks are not required for this remediation PRD.

## Further Notes

- This PRD depends on PRD28's full-repository reprocess API/request mode for the cross-workflow repair action.
- This PRD intentionally keeps index rebuilds manual because existing readiness semantics make stale state visible and explicit rebuilds avoid surprising long-running work.
- If reprocess duration becomes disruptive for larger repositories, a later PRD can add persisted jobs and progress reporting without changing the user-facing repair entry points.
