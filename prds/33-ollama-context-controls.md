# PRD 33: Ollama Context Controls

**Status:** Backlog.

## Problem Statement

Researchers using Chat Workspace can tune retrieval defaults and inspect the retrieved context sent to the local model, but they cannot control the Ollama model context window from the app. This makes long-context RAG behavior harder to reason about: a user may increase top-k, add history, or use a larger prompt without knowing whether the configured local model will have enough runtime context to hold the assembled messages.

Ollama now exposes context-length controls through the app/server defaults and through native API options. Larger windows can materially improve heavy RAG, coding, agentic, and research workflows, but they also increase memory use and can cause CPU offload or failed local requests on smaller machines. The app needs a visible, repository-scoped way to set sane defaults, a Chat Workspace way to see and optionally override the effective context setting, and context-inspection snapshots that make the chosen value reproducible.

## Solution

Add first-class Ollama context controls for local chat:

- Store a repository default for Ollama chat context length alongside the existing chat model default.
- Pass the configured context length to native Ollama `/api/chat` requests using runtime options when a value is set.
- Let Chat Workspace display the effective context value and optionally override it per chat session, while keeping retrieval controls separate from model-runtime controls.
- Include the effective context value in draft context preview and persisted assistant-message context inspection.
- Show memory/performance guidance in Settings / Models and Chat Workspace so users understand that larger context windows require more VRAM/RAM and should be verified with Ollama readiness checks.

## User Stories

1. As a researcher, I want to see the default Ollama context length in Settings / Models, so that chat runtime behavior is visible next to the selected local model.
2. As a researcher, I want to leave context length on Auto, so that Ollama can use its configured app/server/default behavior when I do not need a custom window.
3. As a researcher, I want to choose common context presets such as 4k, 8k, 16k, 32k, 64k, 128k, and 256k, so that I can tune local chat without editing Ollama server environment variables or Modelfiles.
4. As a researcher, I want to enter a custom context length within validated limits, so that advanced local models can use a model-specific window when presets are not enough.
5. As a researcher, I want Settings / Models to explain the memory tradeoff of larger context windows, so that I do not accidentally overload a small workstation.
6. As a researcher, I want new Chat Workspace sessions to inherit the repository context default, so that chat starts from the intended local model configuration.
7. As a researcher, I want existing chat sessions to preserve their effective context setting, so that changing repository defaults does not silently change old conversations.
8. As a researcher, I want to override context length for the active chat session, so that one conversation can test a larger or smaller runtime window without changing repository defaults.
9. As a researcher, I want the Chat Workspace effective summary to show model, retrieval, and context length together, so that the actual request shape is understandable before I ask.
10. As a researcher, I want draft context preview to include the configured context length, so that inspection matches the next local model call.
11. As a researcher, I want persisted assistant-message inspection to show the context length used for that answer, so that old answers remain auditable after settings change.
12. As a researcher, I want readiness guidance to mention `ollama ps` and offload checks, so that I can diagnose slow or failed large-context runs.
13. As a maintainer, I want context controls modeled separately from retrieval settings, so that source selection and model runtime options do not become tangled.
14. As a maintainer, I want the Ollama chat provider to omit `num_ctx` when context length is Auto, so that default Ollama behavior remains unchanged for existing users.
15. As a maintainer, I want deterministic tests around schema validation, API payloads, session inheritance, and inspector snapshots, so that context controls do not regress chat reproducibility.
16. As a maintainer, I want export/recreate bundles to preserve repository context defaults and session snapshots, so that restored repositories behave predictably.

## Implementation Decisions

- Use native Ollama `/api/chat` as the integration boundary. The existing provider already calls this endpoint, and Ollama supports runtime options there.
- Add a nullable repository setting for Ollama chat context length. Null means Auto and must not send a `num_ctx` override.
- Model chat generation/runtime settings separately from retrieval defaults. Retrieval settings continue to own mode, top-k, candidate pool, reranker strategy, filters, and metadata boosts.
- Add a chat-session-level generation settings snapshot so existing sessions keep their effective context behavior when repository defaults change.
- Extend chat create, ask, and context-preview contracts only as much as needed to carry generation settings. The rename endpoint should remain title-only.
- Persist effective generation settings in assistant-message context-inspection metadata alongside model, prompt, retrieval settings, retrieved entries, history, and assembled messages.
- Show Settings / Models as the durable default surface and Chat Workspace as the effective/session override surface.
- Keep Prompt Sandbox unchanged in the first implementation unless the backend generation-settings model can be reused without widening scope. Sandbox-specific context experiments can be a follow-up if users need side-by-side `num_ctx` comparisons.
- Treat common preset labels as UI affordances over integer token values. Avoid model-specific hard caps unless reliable local metadata is available.
- Use conservative validation limits so obvious invalid values are rejected before reaching Ollama. Backend validation remains the source of truth.
- Do not create or manage derived Ollama Modelfiles for this feature. That path is only needed for OpenAI-compatible endpoints or users who prefer model aliases.

## Testing Decisions

- Unit tests should cover repository settings validation for Auto, supported preset-sized values, custom valid values, and invalid small/large/non-integer values.
- Unit tests should cover the Ollama chat provider payload: Auto omits `options.num_ctx`; explicit context includes `options.num_ctx`; existing message formatting is unchanged.
- Backend integration tests should verify new chat sessions inherit repository generation defaults and existing sessions preserve their saved generation settings after repository defaults change.
- Backend integration tests should verify ask and context-preview use the same effective generation settings and persisted assistant snapshots include them.
- Frontend contract tests should verify Settings / Models renders the context control, validates bad values, saves/cancels changes, and reports chat-default impact.
- Frontend contract tests should verify Chat Workspace displays effective context, can override it for a session, sends it with ask/preview requests, and shows it in the inspector.
- Export/recreate tests should verify repository context defaults round-trip through portable bundles. Session-level snapshots should remain inspectable after recreate when chat history is included.
- Default CI should mock Ollama and remain deterministic. Optional live tests can document manual verification with a locally installed model and `ollama ps`, but should not be required for normal CI.

## Out of Scope

- Automatically detecting exact per-model maximum context windows from Ollama model metadata.
- Automatically choosing context length based on host VRAM, RAM, model size, or current `ollama ps` state.
- Managing Ollama app settings, server environment variables, Flash Attention, K/V cache quantization, or model preload/keep-alive policies.
- Creating derived Ollama models with Modelfiles.
- Adding cloud model provider context controls.
- Implementing full token-budget packing, prompt truncation, or history summarization.
- Adding multimodal image-token budgeting.
- Changing retrieval ranking, chunking, embedding, reranking, citation parsing, or prompt-library semantics.
- Making Prompt Sandbox a full context-window experiment manager in the first implementation.

## Further Notes

- Ollama documentation defines context length as the maximum number of tokens available to the model in memory and notes that larger context lengths increase memory requirements.
- Ollama recommends at least 64k context for large-context workflows such as web search, agents, and coding tools.
- Ollama native API requests can specify context length with `options.num_ctx`; Ollama's OpenAI-compatible API path does not support per-request context size and requires a Modelfile-derived model instead.
- The app currently uses native `/api/chat`, so a per-request `num_ctx` option is the right implementation path.
- The existing Settings / Models PRD already called for chat model defaults and context defaults. This PRD completes that missing local-chat context portion without reopening completed model registry or retrieval-defaults work.
