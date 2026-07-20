from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

ChatModelRole = Literal[
    "recommended_default",
    "balanced_local",
    "larger_local",
    "reasoning_experimental",
]


@dataclass(frozen=True)
class ChatModelInfo:
    name: str
    label: str
    role: ChatModelRole
    required: bool = False
    notes: str | None = None
    setup_command: str | None = None
    local_resource_notes: str | None = None
    context_window_notes: str | None = None
    readiness_required: bool = True


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatCompletion:
    content: str
    model: str


class ChatLLM(Protocol):
    def complete(self, *, model: str, messages: list[ChatMessage]) -> ChatCompletion:
        """Return one assistant completion for a chat prompt."""

    def smoke(self, *, model: str) -> ChatCompletion:
        """Return a minimal completion for local setup diagnostics."""


MODEL_REGISTRY: list[ChatModelInfo] = [
    ChatModelInfo(
        name="gemma3:4b",
        label="Gemma 3 4B",
        role="recommended_default",
        required=True,
        notes="Default local chat baseline for small developer machines.",
        setup_command="ollama pull gemma3:4b",
        local_resource_notes="Small enough for routine local RAG smoke tests.",
        context_window_notes="Use the normal repository-context prompt; keep top-k modest on memory-constrained machines.",
    ),
    ChatModelInfo(
        name="llama3.2:3b",
        label="Llama 3.2 3B",
        role="balanced_local",
        notes="Alternative small local chat model for repository-grounded answers.",
        setup_command="ollama pull llama3.2:3b",
        local_resource_notes="Good fit for quick readiness checks and lightweight local chat.",
        context_window_notes="Supports the generic Ollama chat contract; validate answer quality per corpus.",
    ),
    ChatModelInfo(
        name="qwen2.5:7b",
        label="Qwen 2.5 7B",
        role="balanced_local",
        notes="Recommended general-purpose local chat option when more memory is available.",
        setup_command="ollama pull qwen2.5:7b",
        local_resource_notes="Expect higher memory use and latency than the default 4B model.",
        context_window_notes="Keep retrieved context within the model's local runtime limits.",
    ),
    ChatModelInfo(
        name="gemma4:e4b",
        label="Gemma 4 E4B",
        role="balanced_local",
        notes="Locally tested Gemma 4 option for repository-grounded chat on capable workstations.",
        setup_command="ollama pull gemma4:e4b",
        local_resource_notes="Optional local model; expect more memory and latency than the default 4B baseline.",
        context_window_notes="Uses the generic Ollama /api/chat path with chat-owned retrieval context.",
    ),
    ChatModelInfo(
        name="gemma4:12b",
        label="Gemma 4 12B",
        role="larger_local",
        notes="Larger Gemma 4 local option for deeper repository chat when host memory allows.",
        setup_command="ollama pull gemma4:12b",
        local_resource_notes="Not required for default setup or CI; run readiness before long sessions.",
        context_window_notes="Keep top-k and reranking settings within local runtime memory limits.",
    ),
    ChatModelInfo(
        name="qwen3.6",
        label="Qwen 3.6",
        role="balanced_local",
        notes="Locally relevant Qwen chat option available through the standard Ollama chat contract.",
        setup_command="ollama pull qwen3.6",
        local_resource_notes="Optional workstation model; validate latency and answer style per corpus.",
        context_window_notes="Normal repository-context prompting is used unless future testing shows special handling is needed.",
    ),
    ChatModelInfo(
        name="qwen3.5:9b",
        label="Qwen 3.5 9B",
        role="larger_local",
        notes="Higher-capacity Qwen option for hosts with enough local memory.",
        setup_command="ollama pull qwen3.5:9b",
        local_resource_notes="Optional and not part of deterministic CI; smoke-check before use.",
        context_window_notes="Use the same chat-owned retrieval settings as other local Ollama models.",
    ),
    ChatModelInfo(
        name="mistral:7b",
        label="Mistral 7B",
        role="balanced_local",
        notes="General-purpose local model supported through the generic Ollama chat provider.",
        setup_command="ollama pull mistral:7b",
        local_resource_notes="Useful comparison point for local scientific chat quality.",
        context_window_notes="Uses the same text-chat prompt path as other ordinary Ollama models.",
    ),
    ChatModelInfo(
        name="llama3.1:8b",
        label="Llama 3.1 8B",
        role="larger_local",
        notes="Larger local option for machines with more memory.",
        setup_command="ollama pull llama3.1:8b",
        local_resource_notes="Not required for default development or CI.",
        context_window_notes="Prefer explicit readiness checks before using in long RAG sessions.",
    ),
    ChatModelInfo(
        name="deepseek-r1:8b",
        label="DeepSeek R1 8B",
        role="reasoning_experimental",
        notes="Reasoning-oriented local model; answer style may need review before promotion.",
        setup_command="ollama pull deepseek-r1:8b",
        local_resource_notes="Optional experimental model; not a default recommendation.",
        context_window_notes="May emit reasoning-style responses; use focused follow-up work if output formatting needs stricter control.",
    ),
]


class OllamaUnavailableError(RuntimeError):
    """Raised when the local Ollama runtime or configured model is unavailable."""

    def __init__(
        self,
        message: str,
        *,
        readiness_status: str = "unavailable_runtime",
    ) -> None:
        super().__init__(message)
        self.readiness_status = readiness_status


class OllamaChatLLM:
    def __init__(self, base_url: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, *, model: str, messages: list[ChatMessage]) -> ChatCompletion:
        payload = self._post_chat(model=model, messages=messages)
        message = payload.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaUnavailableError(
                "Ollama returned an unexpected chat response.",
                readiness_status="failed",
            )
        return ChatCompletion(content=message["content"], model=str(payload.get("model") or model))

    def smoke(self, *, model: str) -> ChatCompletion:
        return self.complete(
            model=model,
            messages=[
                ChatMessage(
                    role="user",
                    content="Reply with exactly: local model ready [1]",
                )
            ],
        )

    def _post_chat(self, *, model: str, messages: list[ChatMessage]) -> dict[str, object]:
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": message.role, "content": message.content} for message in messages
                    ],
                    "stream": False,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise OllamaUnavailableError(
                    f"Ollama model '{model}' is not installed. Run `ollama pull {model}`.",
                    readiness_status="not_installed",
                ) from exc
            raise OllamaUnavailableError(
                f"Ollama chat request failed for model '{model}'. "
                "Check the local Ollama logs and rerun the smoke test.",
                readiness_status="failed",
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaUnavailableError(
                f"Ollama is not reachable at {self.base_url}. Start Ollama, then run `ollama pull {model}` if needed.",
                readiness_status="unavailable_runtime",
            ) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise OllamaUnavailableError(
                "Ollama returned a response that was not valid JSON.",
                readiness_status="failed",
            ) from exc
        if not isinstance(payload, dict):
            raise OllamaUnavailableError(
                "Ollama returned an unexpected response body.",
                readiness_status="failed",
            )
        return payload
