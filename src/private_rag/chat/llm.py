from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class ChatModelInfo:
    name: str
    label: str
    role: str
    required: bool = False
    notes: str | None = None


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


MODEL_REGISTRY = [
    ChatModelInfo(
        name="gemma3:4b",
        label="Gemma 3 4B",
        role="default-small-mac",
        required=True,
        notes="Initial PRD7 local chat baseline.",
    ),
    ChatModelInfo(
        name="gemma4:12b",
        label="Gemma 4 12B",
        role="later-windows-baseline",
        notes="Larger follow-up baseline; not required for CI or default development.",
    ),
    ChatModelInfo(
        name="qwen3.5:9b",
        label="Qwen 3.5 9B",
        role="later-windows-baseline",
        notes="Larger follow-up baseline; not required for CI or default development.",
    ),
]


class OllamaUnavailableError(RuntimeError):
    """Raised when the local Ollama runtime or configured model is unavailable."""


class OllamaChatLLM:
    def __init__(self, base_url: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, *, model: str, messages: list[ChatMessage]) -> ChatCompletion:
        payload = self._post_chat(model=model, messages=messages)
        message = payload.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaUnavailableError("Ollama returned an unexpected chat response.")
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
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError(
                f"Ollama is not reachable or model '{model}' is unavailable. "
                f"Start Ollama and run `ollama pull {model}`."
            ) from exc
        payload = response.json()
        if not isinstance(payload, dict):
            raise OllamaUnavailableError("Ollama returned an unexpected response body.")
        return payload
