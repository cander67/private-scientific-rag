# PRD 25: Chat Context Inspection

**Status:** Ready for final review.

## Problem Statement

Researchers using Chat Workspace need to understand exactly what context is sent to the local LLM. Today the app persists chat messages, retrieval runs, and citations, and Prompt Sandbox stores context snapshots, but normal chat does not expose the assembled prompt, prior chat history, retrieved chunks, retrieval settings, and model payload in one inspectable view.

That makes prompt tuning and retrieval debugging harder. A researcher can see the final answer and citations, but cannot easily answer: which retrieved chunks were included, which prior messages were sent, which system prompt was active, and what the LLM actually received?

## Solution

Add an `Inspect context` workflow to Chat Workspace. The workflow should let a researcher preview the payload that would be sent for the current draft question and inspect the payload that was sent for a completed assistant response. The view should show the active model, retrieval settings, active chat prompt, included chat history, retrieved context entries, and final message list in a readable pop-out or modal.

The inspection surface is for transparency and debugging. It should not become Prompt Sandbox or a prompt editor, and it should not leak data outside the local app.

## User Stories

1. As a researcher, I want to click `Inspect context` before sending a question, so that I can see the prompt and retrieved context that would go to the LLM.
2. As a researcher, I want to inspect the context for an existing assistant answer, so that I can audit why the model responded the way it did.
3. As a researcher, I want the context inspector to include retrieved chunks with citation IDs, titles, pages, sections, ranks, and scores, so that I can evaluate retrieval quality.
4. As a researcher, I want the inspector to include the active system prompt and prompt library entry name, so that prompt changes are traceable.
5. As a researcher, I want the inspector to include the recent chat history sent to the model, so that I can understand conversational carryover.
6. As a researcher, I want the inspector to include the selected model and retrieval settings, so that a context snapshot is reproducible.
7. As a researcher, I want empty or insufficient context to be explicit, so that I can distinguish retrieval failure from model behavior.
8. As a maintainer, I want chat context preview built on the same prompt assembly logic as actual chat, so that inspection and execution cannot drift.
9. As a maintainer, I want deterministic tests for the inspector payload, so that future prompt or history changes are visible.

## Implementation Decisions

- Add a chat context inspection API that returns a structured payload using the same retrieval and prompt assembly path as normal chat.
- Support preview for an unsent question and inspection for a persisted assistant message or retrieval run where enough data is available.
- Include structured sections for model, repository, prompt, retrieval settings, chat history, retrieved context entries, and final LLM messages.
- Preserve the existing Chat Workspace citation and Source Viewer navigation behavior.
- Use a pop-out style modal or secondary panel in Chat Workspace, not a separate top-level route.
- Keep Prompt Sandbox as the owner of side-by-side prompt/retrieval/model experimentation.
- Do not call remote services or export data as part of inspection.

## Testing Decisions

- Unit tests should verify inspected payload assembly uses the same system prompt, history limit, context formatting, and user question as normal chat.
- Integration tests should verify preview and persisted-message inspection responses for a repository-scoped chat session.
- Frontend contract tests should verify the `Inspect context` control, modal/panel sections, empty context messaging, and links back to source context.
- Tests should use fake retrieval, fake embeddings, fake reranker, and fake LLM boundaries; live Ollama checks remain opt-in and out of scope.

## Out of Scope

- Prompt editing inside the inspector.
- Side-by-side model comparisons.
- Cloud model payloads.
- Long-term audit/export reports beyond the existing local database and export bundle scope.
- Changing chat retrieval defaults.

## Further Notes

- This PRD comes from user testing after PRD23 baseline work.
- Prompt Sandbox already has context snapshots for experimental runs; this PRD brings equivalent transparency to normal chat without merging the two workflows.
