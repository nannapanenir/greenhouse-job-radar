"""Shared client for OpenAI-compatible chat-completion APIs
(OpenRouter, Gemini's OpenAI endpoint, Ollama/LM Studio/llama.cpp/vLLM)."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .base import AIError, AIProvider, Message


class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        extra_body: Optional[dict[str, Any]] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        super().__init__(model)
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._extra_headers = extra_headers or {}
        self._extra_body = extra_body or {}
        self._transport = transport  # injectable for tests

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self._extra_headers}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _connect_error(self, error: Exception) -> AIError:
        return AIError(f"Couldn't reach {self.label}: {type(error).__name__}.")

    async def complete(self, messages: list[Message], *, temperature: float = 0.1, timeout: float = 60.0) -> str:
        body = {"model": self.model, "messages": messages, "temperature": temperature, **self._extra_body}
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=timeout) as client:
                response = await client.post(f"{self.base_url}/chat/completions", json=body, headers=self._headers())
        except httpx.TimeoutException:
            raise AIError(
                f"{self.label} did not respond within {round(timeout)}s. This model may be too slow/overloaded — "
                "try again, or switch models in Settings."
            ) from None
        except httpx.HTTPError as error:
            raise self._connect_error(error) from None

        if not 200 <= response.status_code < 300:
            message = response.text[:300]
            try:
                message = response.json().get("error", {}).get("message") or message
            except (ValueError, AttributeError):
                pass
            status = response.status_code
            raise AIError(
                f"{self.label} error ({status}): {message}",
                status=status,
                retryable=status == 429 or status >= 500,
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise AIError(f"Failed to parse {self.label} response: {error}") from None
        if isinstance(content, list):  # some servers return content parts
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if not content:
            raise AIError(
                f"{self.label} returned an empty response — the model may be overloaded or unavailable right now. "
                "Try again, or switch models in Settings."
            )
        return content
