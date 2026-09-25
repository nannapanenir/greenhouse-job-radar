import asyncio
import json

import httpx
import pytest

from backend import config
from backend.ai import AIError, GeminiProvider, LocalProvider, OpenRouterProvider, complete_with_retry, create_provider
from backend.ai.base import extract_json_object

MESSAGES = [{"role": "user", "content": "hi"}]


def reply(content="hello", status=200):
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})


def run(coro):
    return asyncio.run(coro)


def test_openrouter_request_shape():
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), headers=request.headers, body=json.loads(request.content))
        return reply("ok")

    provider = OpenRouterProvider(model="openai/gpt-4o-mini", api_key="sk-or-secret", transport=httpx.MockTransport(handler))
    assert run(provider.complete(MESSAGES)) == "ok"
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["headers"]["authorization"] == "Bearer sk-or-secret"
    assert seen["headers"]["x-title"] == "Job Radar"
    assert seen["body"]["reasoning"] == {"effort": "low", "exclude": True}
    assert seen["body"]["model"] == "openai/gpt-4o-mini" and seen["body"]["temperature"] == 0.1


def test_local_provider_no_key_and_no_openrouter_extensions():
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), headers=request.headers, body=json.loads(request.content))
        return reply("local")

    provider = LocalProvider(model="llama3.2:3b", base_url="http://localhost:11434/v1/", transport=httpx.MockTransport(handler))
    assert run(provider.complete(MESSAGES)) == "local"
    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert "authorization" not in seen["headers"] and "reasoning" not in seen["body"]


def test_gemini_uses_openai_compatible_endpoint():
    seen = {}
    provider = GeminiProvider(model="gemini-2.0-flash", api_key="g-key",
                              transport=httpx.MockTransport(lambda r: seen.update(url=str(r.url)) or reply("gem")))
    assert run(provider.complete(MESSAGES)) == "gem"
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def test_errors_and_retry_policy():
    calls = []

    def flaky(request):
        calls.append(1)
        return httpx.Response(429, json={"error": {"message": "rate limited"}}) if len(calls) < 3 else reply("third time")

    provider = OpenRouterProvider(model="m", api_key="k", transport=httpx.MockTransport(flaky))
    assert run(complete_with_retry(provider, MESSAGES, sleep=lambda s: asyncio.sleep(0))) == "third time"
    assert len(calls) == 3

    calls.clear()
    bad_key = OpenRouterProvider(model="m", api_key="k", transport=httpx.MockTransport(
        lambda r: calls.append(1) or httpx.Response(401, json={"error": {"message": "No auth"}})))
    with pytest.raises(AIError) as err:
        run(complete_with_retry(bad_key, MESSAGES, sleep=lambda s: asyncio.sleep(0)))
    assert "OpenRouter error (401): No auth" in str(err.value) and len(calls) == 1  # 4xx: no retry


def test_empty_content_timeout_and_connection_messages():
    empty = OpenRouterProvider(model="m", api_key="k", transport=httpx.MockTransport(lambda r: reply("")))
    with pytest.raises(AIError, match="empty response"):
        run(empty.complete(MESSAGES))

    def timeout(request):
        raise httpx.ReadTimeout("slow")
    with pytest.raises(AIError, match="did not respond within 3s"):
        run(OpenRouterProvider(model="m", api_key="k", transport=httpx.MockTransport(timeout)).complete(MESSAGES, timeout=3))

    def refused(request):
        raise httpx.ConnectError("refused")
    with pytest.raises(AIError, match="Couldn't reach the local server at http://localhost:1234/v1"):
        run(LocalProvider(model="m", base_url="http://localhost:1234/v1", transport=httpx.MockTransport(refused)).complete(MESSAGES))


def test_content_parts_are_joined():
    parts = httpx.Response(200, json={"choices": [{"message": {"content": [{"type": "text", "text": "a"}, {"text": "b"}]}}]})
    provider = LocalProvider(model="m", base_url="http://x/v1", transport=httpx.MockTransport(lambda r: parts))
    assert run(provider.complete(MESSAGES)) == "ab"


def test_create_provider_from_settings(monkeypatch):
    assert create_provider(config.AISettings()) is None
    assert isinstance(create_provider(config.AISettings("openrouter", "m", api_key="k")), OpenRouterProvider)
    assert isinstance(create_provider(config.AISettings("local", "m", base_url="http://x/v1")), LocalProvider)
    assert isinstance(create_provider(config.AISettings("gemini", "m", api_key="k")), GeminiProvider)
    assert create_provider(config.AISettings("local", "m")) is None  # local needs a URL


def test_settings_file_env_precedence_and_no_key_exposure(monkeypatch):
    status = config.save_ai_settings("openrouter", "openai/gpt-4o-mini", "sk-or-TOPSECRET").public_status()
    assert status["configured"] and status["source"] == "file" and status["hasApiKey"]
    assert "sk-or-TOPSECRET" not in json.dumps(status)
    assert config.settings_file().stat().st_mode & 0o777 == 0o600
    # blank key keeps the stored one when only the model changes
    assert config.save_ai_settings("openrouter", "other/model").api_key == "sk-or-TOPSECRET"
    with pytest.raises(config.SettingsError):
        config.save_ai_settings("local", "llama")  # URL required
    assert not config.clear_ai_settings().configured

    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_MODEL", "gemini-2.0-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    settings = config.load_ai_settings()
    assert settings.provider == "gemini" and settings.api_key == "env-key" and settings.source == "env"
    assert settings.public_status()["editable"] is False
    with pytest.raises(config.SettingsError):
        config.save_ai_settings("openrouter", "m", "k")


@pytest.mark.parametrize("raw, expected", [
    ('{"a": 1}', {"a": 1}),
    ("<think>hmm {not json}</think>\n```json\n{\"a\": 2}\n```", {"a": 2}),
    ('Sure! {"a": {"b": [1]}} Cheers', {"a": {"b": [1]}}),
])
def test_extract_json_object(raw, expected):
    assert extract_json_object(raw) == expected


def test_extract_json_object_errors():
    with pytest.raises(ValueError, match="No JSON object found"):
        extract_json_object("nothing here")
    with pytest.raises(ValueError, match="failed to parse"):
        extract_json_object('{"a": 1,}')
