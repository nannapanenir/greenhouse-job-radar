"""Provider overload handling (seen in production: Gemini 503 "high demand")."""

import asyncio
import json

import httpx
import pytest

from backend import config
from backend.ai import AIError, GeminiProvider, complete_with_retry, create_provider

MESSAGES = [{"role": "user", "content": "hi"}]
GEMINI_503 = [{"error": {"code": 503, "status": "UNAVAILABLE",
                         "message": "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later."}}]


def ok(content="done"):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def no_sleep(seconds):
    return asyncio.sleep(0)


def test_gemini_list_shaped_error_is_readable():
    provider = GeminiProvider(model="gemini-x", api_key="secret-key",
                              transport=httpx.MockTransport(lambda r: httpx.Response(503, json=GEMINI_503)))
    with pytest.raises(AIError) as err:
        asyncio.run(provider.complete(MESSAGES))
    message = str(err.value)
    assert message.startswith("Gemini error (503): gemini-x is temporarily overloaded or rate-limited")
    assert "experiencing high demand" in message and "AI_FALLBACK_MODEL" in message
    assert "[{" not in message and "secret-key" not in message
    assert err.value.retryable


def test_fallback_model_used_after_primary_overload():
    models = []

    def handler(request):
        model = json.loads(request.content)["model"]
        models.append(model)
        return httpx.Response(503, json=GEMINI_503) if model == "primary" else ok(f"answer from {model}")

    provider = GeminiProvider(model="primary", api_key="k", transport=httpx.MockTransport(handler))
    provider.fallback_models = ["backup-a", "backup-b"]
    result = asyncio.run(complete_with_retry(provider, MESSAGES, per_attempt_timeout=25, total_budget=50, sleep=no_sleep))
    assert result == "answer from backup-a"
    assert models == ["primary", "primary", "primary", "backup-a"]
    assert provider.model == "primary"  # original provider untouched


def test_no_fallback_for_client_errors():
    models = []

    def handler(request):
        models.append(json.loads(request.content)["model"])
        return httpx.Response(401, json={"error": {"message": "API key not valid"}})

    provider = GeminiProvider(model="primary", api_key="k", transport=httpx.MockTransport(handler))
    provider.fallback_models = ["backup"]
    with pytest.raises(AIError, match="401"):
        asyncio.run(complete_with_retry(provider, MESSAGES, per_attempt_timeout=25, total_budget=50, sleep=no_sleep))
    assert models == ["primary"]


def test_all_models_overloaded_reports_last_error_within_budget():
    now = [0.0]

    def handler(request):
        now[0] += 3
        return httpx.Response(503, json=GEMINI_503)

    async def sleep(seconds):
        now[0] += seconds

    provider = GeminiProvider(model="primary", api_key="k", transport=httpx.MockTransport(handler))
    provider.fallback_models = ["backup"]
    with pytest.raises(AIError, match="backup is temporarily overloaded"):
        asyncio.run(complete_with_retry(provider, MESSAGES, per_attempt_timeout=25, total_budget=50,
                                        sleep=sleep, clock=lambda: now[0]))
    assert now[0] <= 50


def test_fallback_models_from_environment(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_MODEL", "primary")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("AI_FALLBACK_MODEL", "backup-a, primary ,backup-b")
    settings = config.load_ai_settings()
    assert settings.public_status()["fallbackModels"] == ["backup-a", "primary", "backup-b"]
    assert create_provider(settings).fallback_models == ["backup-a", "backup-b"]  # primary not repeated
