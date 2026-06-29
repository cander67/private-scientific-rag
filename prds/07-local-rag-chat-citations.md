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

## Documentation References

- Ollama documentation: https://docs.ollama.com/
- Ollama `gemma3:4b`: https://ollama.com/library/gemma3:4b
- Ollama `gemma4:12b`: https://ollama.com/library/gemma4:12b
- Ollama `qwen3.5:9b`: https://ollama.com/library/qwen3.5:9b
- `frontend/README.md` for UI setup.
