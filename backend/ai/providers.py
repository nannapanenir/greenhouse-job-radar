"""Concrete providers. Add a new one by subclassing OpenAICompatibleProvider
(or AIProvider for non-OpenAI-compatible APIs) and registering it in
``create_provider``."""

from __future__ import annotations

from typing import Optional

import httpx

from ..config import AISettings
from .base import AIError, AIProvider
from .openai_compatible import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "openrouter"
    label = "OpenRouter"
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, *, model: str, api_key: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        super().__init__(
            model=model,
            base_url=self.BASE_URL,
            api_key=api_key,
            extra_headers={"HTTP-Referer": "http://localhost", "X-Title": "Job Radar"},
            # OpenRouter-specific: keep reasoning models fast and their thoughts out of the answer.
            extra_body={"reasoning": {"effort": "low", "exclude": True}},
            transport=transport,
        )


class LocalProvider(OpenAICompatibleProvider):
    """Any OpenAI-compatible local server (Ollama, LM Studio, llama.cpp, vLLM)."""

    name = "local"
    label = "Local server"

    def __init__(self, *, model: str, base_url: str, api_key: Optional[str] = None,
                 transport: Optional[httpx.AsyncBaseTransport] = None):
        super().__init__(model=model, base_url=base_url, api_key=api_key, transport=transport)

    def _connect_error(self, error: Exception) -> AIError:
        return AIError(
            f"Couldn't reach the local server at {self.base_url}. Make sure it's running and the URL/port in Settings is correct."
        )


class GeminiProvider(OpenAICompatibleProvider):
    """Google Gemini via its OpenAI-compatible endpoint (GEMINI_API_KEY)."""

    name = "gemini"
    label = "Gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

    def __init__(self, *, model: str, api_key: str, transport: Optional[httpx.AsyncBaseTransport] = None):
        super().__init__(model=model, base_url=self.BASE_URL, api_key=api_key, transport=transport)


def create_provider(settings: AISettings, transport: Optional[httpx.AsyncBaseTransport] = None) -> Optional[AIProvider]:
    """Provider for the current settings, or None when AI is not configured."""
    if not settings.configured:
        return None
    if settings.provider == "local":
        provider = LocalProvider(model=settings.model, base_url=settings.base_url, api_key=settings.api_key, transport=transport)
    elif settings.provider == "gemini":
        provider = GeminiProvider(model=settings.model, api_key=settings.api_key, transport=transport)
    else:
        provider = OpenRouterProvider(model=settings.model, api_key=settings.api_key, transport=transport)
    provider.fallback_models = [m for m in settings.fallback_models if m != settings.model]
    return provider
