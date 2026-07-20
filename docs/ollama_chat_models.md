# Ollama Chat Models

PRD22 keeps one generic Ollama chat provider for ordinary local text-chat models. The provider sends the selected repository or sandbox model name to Ollama's `/api/chat` endpoint, so most new chat models are settings and registry work rather than new adapter work.

PRD23 user-testing remediation should add current local workstation choices to the known model catalog, including `gemma4:e4b`, `gemma4:12b`, `qwen3.6`, and `qwen3.5:9b`, with setup commands and resource notes. These remain optional local models; default CI and default setup should not require them.

## Generic Model Contract

An Ollama chat model can use the existing RAG chat and Prompt Sandbox path when it:

- is installed in the local Ollama runtime;
- responds to `POST /api/chat` with a normal assistant message;
- can follow the repository-context prompt without special formatting;
- fits the retrieved context selected by the user-facing top-k controls.

Repository settings store the active chat model string in `model.ollama_chat_model`. New Chat Workspace sessions use that saved value by default, and Prompt Sandbox runs persist the model that produced each answer.

Normal Chat Workspace sessions are repository-grounded by default. They use chat-owned retrieval settings, retrieve local repository context, and send that context to the selected Ollama chat model. Search Lab settings do not implicitly carry over to chat.

## Adding A Recommended Registry Entry

Add ordinary recommended models by editing `MODEL_REGISTRY` in `src/private_rag/chat/llm.py`.

Each entry should include:

- `name`: the Ollama tag, such as `gemma3:4b`;
- `label`: display name for Settings / Models;
- `role`: one of `recommended_default`, `balanced_local`, `larger_local`, or `reasoning_experimental`;
- `setup_command`: usually `ollama pull <model>`;
- `local_resource_notes`: memory/latency expectations;
- `context_window_notes`: practical RAG-context guidance;
- `readiness_required`: `true` for local models that must pass smoke checks before use.

No new provider class is needed when the model supports the normal text-chat contract.

## Custom Local Models

Users can type any local Ollama model name in Settings / Models or Prompt Sandbox. Custom names go through the same readiness and chat boundary as registry models. If the model is missing, readiness should tell the user to run:

```bash
ollama pull <model>
```

Default CI should keep using fake LLM boundaries. Live local model checks stay opt-in.

## When Focused Integration Is Needed

Create a focused follow-up PRD instead of adding only registry metadata when a model needs:

- unusual prompt templates or role formatting;
- special context-window handling beyond top-k/context sizing;
- multimodal inputs;
- tool or function calling;
- enforced structured output;
- custom parsing of reasoning traces or nonstandard responses.

Those cases can still reuse the current registry, but they need explicit product behavior, tests, and documentation before being promoted.

## Live Checks

Install a registry or custom model:

```bash
ollama pull gemma3:4b
```

Run the Ollama boundary smoke:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_ollama_live.py
```

Run the local RAG chat smoke:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_chat_rag_live.py
```

PowerShell:

```powershell
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m live tests/integration/test_ollama_live.py
uv run pytest -m live tests/integration/test_chat_rag_live.py
Remove-Item Env:\RUN_LIVE_TESTS
```
