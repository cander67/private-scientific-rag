# PRD 7: Local RAG Chat with Citations

## Goal

Build local-only RAG chat with repository-grounded answers, inline citations, and clickable citation cards.

## User Stories

- As a researcher, I can ask questions against a repository.
- As a researcher, I can see inline citations for factual claims.
- As a researcher, I can click a citation to inspect the source chunk, page, section, table, or figure.
- As a privacy-conscious user, I can run chat without cloud providers.

## Scope

- Ollama-only LLM client.
- Initial model: `gemma3:4b`.
- Later Windows baselines: `gemma4:12b` and `qwen3.5:9b`.
- Model registry and smoke test.
- Fixed system prompt per repository.
- RAG context builder.
- Chat sessions and messages.
- Citation mapper.
- Chat Workspace UI.

## Acceptance Criteria

- Chat uses retrieved context from the active repository.
- Answers cite source chunks with page/section/table/figure metadata when available.
- Citation cards open and close without losing chat context.
- Each citation maps to stored document/chunk/source metadata.
- Chat persists across browser refresh and backend restart.
- LLM calls can be mocked in tests.

## Test Plan

- Unit test citation mapping.
- Unit test prompt/context assembly.
- Integration test chat with mocked Ollama client.
- UI test citation card open/close behavior.

## Implemented Defaults and Tradeoffs

- Chat uses Ollama through a mockable local LLM boundary; the first default model is `gemma3:4b`.
- Chat retrieval settings are owned by each chat session and can be adjusted in Chat Workspace. They do not inherit Search Lab settings.
- Chat does not rebuild indexes automatically. Users explicitly rebuild full-text/vector indexes and check local model readiness in Chat Workspace.
- Repository system prompts are stored in repository settings as a prompt library with an active chat prompt ID.
- Assistant answers are expected to emit inline citation tokens like `[1]`; mapped citations are persisted with assistant messages and resolve to stored document/chunk metadata.
- Live Ollama tests are opt-in and separate from default CI. Default CI uses mocked LLM calls and deterministic fixtures.

## Documentation References

- Ollama documentation: https://docs.ollama.com/
- Ollama `gemma3:4b`: https://ollama.com/library/gemma3:4b
- Ollama `gemma4:12b`: https://ollama.com/library/gemma4:12b
- Ollama `qwen3.5:9b`: https://ollama.com/library/qwen3.5:9b
- `frontend/README.md` for UI setup.
