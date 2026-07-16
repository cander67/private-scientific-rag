# PRD 22: Ollama Chat Model Expansion

## Goal

Let researchers use additional local Ollama chat models in RAG chat and Prompt Sandbox without adding one-off integration code for every model, while preserving clear setup, readiness, and model-metadata reporting.

## User Stories

- As a researcher, I can choose additional Ollama chat models from the known model registry.
- As a researcher, I can enter a custom local Ollama chat model name and use it when it supports the normal Ollama chat API.
- As a maintainer, I can add a recommended Ollama chat model by updating registry metadata rather than writing a new provider.
- As a maintainer, I can identify when a model needs focused work because it requires unusual prompting, context handling, multimodal input, tool use, or structured output behavior.
- As a researcher, I can see which chat model produced a chat or sandbox response.

## Scope

- Expand the chat model registry with additional known/recommended Ollama chat models.
- Keep the existing generic Ollama chat provider as the main integration path for ordinary text-chat models.
- Allow known registry models and custom local Ollama model names to flow through the same readiness checks.
- Surface setup and smoke-test errors clearly, including missing Ollama runtime and missing model cases.
- Verify model selection in RAG chat and Prompt Sandbox.
- Document when adding a new Ollama chat model is registry-only versus when focused integration work is needed.

## Out Of Scope

- Remote hosted chat APIs.
- Non-Ollama chat runtimes.
- Model fine-tuning.
- Multimodal chat, tool/function calling, or model-specific structured-output enforcement unless later selected as a dedicated PRD.
- Prompt optimization or evaluation beyond confirming that the selected model works through existing chat and sandbox flows.

## Acceptance Criteria

- Additional known Ollama chat models can be selected through repository settings and used in new RAG chat sessions.
- A custom local Ollama chat model can be configured and smoke-tested through the existing provider when it supports Ollama chat.
- Missing runtime/model cases produce actionable setup guidance.
- Prompt Sandbox uses and records the selected model for each run.
- Docs explain that ordinary Ollama chat models are generic provider/registry work, while special prompting, multimodal, tool, context-window, or structured-output requirements need focused implementation.

## Test Plan

- Unit tests for chat model registry metadata and default selection.
- Deterministic integration tests that verify known and custom model names are passed to the chat boundary.
- Deterministic tests for readiness statuses using a fake chat provider.
- Frontend contract tests for model registry/readiness display when UI changes are made.
- Live/local Ollama chat smoke tests gated behind the existing `live` marker.

## Notes

The current Ollama chat boundary already accepts a model name at call time, so most new text-chat models should not require unique integration code. This PRD makes that generic behavior explicit, improves registry/readiness support, and documents the threshold for a separate model-specific PRD.
