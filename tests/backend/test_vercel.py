"""Vercel deployment contract: entry point, routing, dependencies, read-only
settings, request-size and time budgets."""

import asyncio
import importlib.util
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.ai import AIError
from backend.ai.base import complete_with_retry
from backend.main import app
from backend.resume.parser import MAX_FILE_BYTES
from tests.backend.conftest import FakeProvider

ROOT = Path(__file__).resolve().parents[2]
VERCEL = json.loads((ROOT / "vercel.json").read_text())
VERCEL_BODY_LIMIT = 4.5 * 1000 * 1000  # Vercel Functions request body limit (4.5 MB)


def test_entry_point_exposes_the_existing_app():
    spec = importlib.util.spec_from_file_location("vercel_index", ROOT / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.app is app
    assert (ROOT / "api" / "companies.js").exists()  # Node function preserved


def _to_regex(source: str) -> re.Pattern:
    """Minimal path-to-regexp for the patterns used in vercel.json."""
    if "(" in source:
        return re.compile(f"^{source}$")
    pattern = re.sub(r"/:(\w+)\*", r"(?:/.*)?", source)
    return re.compile(f"^{pattern}$")


def _destination(path: str):
    for rule in VERCEL["rewrites"]:
        if _to_regex(rule["source"]).match(path):
            return rule["destination"]
    return None  # served as-is (static file or api/*.js function)


@pytest.mark.parametrize("path, destination", [
    ("/api/health", "/api/index"),
    ("/api/ai/status", "/api/index"),
    ("/api/ai/settings", "/api/index"),
    ("/api/resume/parse", "/api/index"),
    ("/api/resume/tailor", "/api/index"),
    ("/api/companies", None),             # existing Node function, not intercepted
    ("/", "/index.html"),
    ("/resume-ai", "/index.html"),
    ("/applications", "/index.html"),
    ("/assets/index-abc.js", None),
    ("/data/jobs.json", None),
])
def test_routing(path, destination):
    assert _destination(path) == destination


def test_every_rewritten_api_path_exists_in_fastapi():
    routes = set(app.openapi()["paths"])
    for path in ("/api/health", "/api/ai/status", "/api/ai/settings", "/api/resume/parse", "/api/resume/tailor",
                 "/api/resume/generate", "/api/resume/chat"):
        assert path in routes


def test_function_config_and_time_budget(monkeypatch):
    function = VERCEL["functions"]["api/index.py"]
    monkeypatch.setenv("VERCEL", "1")
    per_attempt, budget = config.ai_timeouts()
    assert per_attempt <= budget < function["maxDuration"]  # AI work finishes inside the function window
    assert "backend/**" in function["includeFiles"]


def test_production_requirements_are_runtime_only():
    lines = [l.split(">")[0].split("=")[0].strip().lower() for l in (ROOT / "requirements.txt").read_text().splitlines()
             if l.strip() and not l.startswith("#")]
    assert {"fastapi", "pydantic", "httpx", "python-multipart", "pymupdf", "python-docx", "reportlab"} <= set(lines)
    assert not {"pytest", "playwright", "uvicorn[standard]", "uvicorn"} & set(lines)


def test_upload_limit_below_vercel_body_limit():
    assert MAX_FILE_BYTES + 64 * 1024 < VERCEL_BODY_LIMIT  # headroom for multipart framing


def test_settings_are_read_only_on_vercel(monkeypatch, tmp_path):
    client = TestClient(app)
    # a settings file that must be ignored in production
    config._write_private_json(config.settings_file(), {"provider": "openrouter", "model": "m", "apiKey": "file-key"})
    monkeypatch.setenv("VERCEL", "1")
    status = client.get("/api/ai/status").json()
    assert status["configured"] is False and status["editable"] is False and status["managedBy"] == "vercel"
    saved = client.post("/api/ai/settings", json={"provider": "gemini", "model": "m", "apiKey": "should-not-persist"})
    assert saved.status_code == 409 and "Vercel environment variables" in saved.json()["detail"]
    assert client.delete("/api/ai/settings").status_code == 409
    assert "should-not-persist" not in config.settings_file().read_text()

    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_API_KEY", "env-secret-value")
    status = client.get("/api/ai/status")
    assert status.json()["configured"] is True and status.json()["provider"] == "gemini"
    assert "env-secret-value" not in status.text


def test_retry_respects_total_budget():
    now = [0.0]
    timeouts = []

    class Slow(FakeProvider):
        async def complete(self, messages, *, temperature=0.1, timeout=60.0):
            timeouts.append(timeout)
            now[0] += timeout            # every attempt times out
            raise AIError("timed out")

    async def fake_sleep(seconds):
        now[0] += seconds

    with pytest.raises(AIError):
        asyncio.run(complete_with_retry(Slow("x"), [], per_attempt_timeout=25, total_budget=50,
                                        sleep=fake_sleep, clock=lambda: now[0]))
    assert timeouts == [25, 23]           # second attempt shrinks to fit; no third attempt
    assert now[0] <= 50


def test_retry_still_retries_transient_errors_within_budget():
    provider = FakeProvider(AIError("503"), "ok")
    assert asyncio.run(complete_with_retry(provider, [], per_attempt_timeout=25, total_budget=50,
                                           sleep=lambda s: asyncio.sleep(0))) == "ok"
