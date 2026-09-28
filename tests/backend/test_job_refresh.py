"""Job Refresh Manager (backend/jobs/refresh.py) and POST /api/jobs/refresh."""

import asyncio
import json
import random
import re
import shutil
from datetime import datetime
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent import main as agent_main
from agent.adapters import ADAPTERS, Company, FetchError, HttpError
from agent.config import settings as agent_settings
from backend.api import jobs as jobs_api
from backend.jobs.refresh import (
    AsyncFixtureTransport,
    RefreshConfig,
    TransientError,
    fetch_company,
    refresh_metadata,
    run_refresh,
    safe_reason,
)
from backend.main import app

ROOT = Path(__file__).resolve().parents[2]
AGENT_FIXTURES = ROOT / "tests" / "agent" / "fixtures"
GREENHOUSE_BOARD = json.loads((AGENT_FIXTURES / "greenhouse" / "anthropic.json").read_text())
client = TestClient(app)


def config(**overrides) -> RefreshConfig:
    values = dict(concurrency=6, request_timeout=5, company_timeout=5, retries=2,
                  backoff_base=0.001, backoff_cap=0.002, budget=30)
    values.update(overrides)
    return RefreshConfig(**values)


class FakeTransport:
    """Scripted per-company behavior; records concurrency and start/end times."""

    def __init__(self, delays=None, script=None, default_delay=0.01):
        self.delays = delays or {}
        self.script = {k: list(v) for k, v in (script or {}).items()}  # key -> [exception | payload, ...]
        self.default_delay = default_delay
        self.active = 0
        self.max_active = 0
        self.calls: dict[str, int] = {}
        self.events: list[tuple[str, str, float]] = []

    async def get_json(self, url, *, source, company_key):
        loop = asyncio.get_running_loop()
        self.calls[company_key] = self.calls.get(company_key, 0) + 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.events.append(("start", company_key, loop.time()))
        try:
            await asyncio.sleep(self.delays.get(company_key, self.default_delay))
            steps = self.script.get(company_key)
            step = steps.pop(0) if steps else {"jobs": []}
            if isinstance(step, Exception):
                raise step
            return step
        finally:
            self.active -= 1
            self.events.append(("end", company_key, loop.time()))

    def time_of(self, kind, key):
        return next(t for k, c, t in self.events if k == kind and c == key)


def greenhouse_tasks(transport, keys):
    adapter = ADAPTERS["greenhouse"](transport)
    return [(adapter, Company(name=k.title(), key=k)) for k in keys]


def run(coro):
    return asyncio.run(coro)


# ---- bounded concurrency -------------------------------------------------------------------------

@pytest.mark.parametrize("limit", [1, 3, 6])
def test_concurrency_limit_is_respected(limit):
    transport = FakeTransport(default_delay=0.02)
    results, _ = run(run_refresh(greenhouse_tasks(transport, [f"c{i}" for i in range(20)]), transport,
                                 config(concurrency=limit)))
    assert transport.max_active == limit
    assert len(results) == 20 and all(r.ok for r in results)


def test_sliding_window_starts_next_company_when_a_slot_frees():
    # concurrency 2: "slow" holds one slot; the others must flow through the second slot
    # while "slow" is still running (a batch implementation would wait for "slow").
    transport = FakeTransport(delays={"slow": 0.4}, default_delay=0.02)
    run(run_refresh(greenhouse_tasks(transport, ["slow", "a", "b", "c", "d"]), transport, config(concurrency=2)))
    slow_end = transport.time_of("end", "slow")
    for key in ("b", "c", "d"):
        assert transport.time_of("start", key) < slow_end
    assert transport.max_active == 2


def test_results_keep_config_order_regardless_of_completion_order():
    transport = FakeTransport(delays={"a": 0.1, "b": 0.01, "c": 0.05})
    results, _ = run(run_refresh(greenhouse_tasks(transport, ["a", "b", "c"]), transport, config(concurrency=3)))
    assert [r.company.key for r in results] == ["a", "b", "c"]


def test_concurrency_from_env(monkeypatch):
    monkeypatch.setenv("JOB_FETCH_CONCURRENCY", "9")
    monkeypatch.setenv("JOB_FETCH_RETRIES", "0")
    cfg = RefreshConfig.from_env()
    assert (cfg.concurrency, cfg.retries) == (9, 0)
    for bad in ("0", "-3", "abc"):
        monkeypatch.setenv("JOB_FETCH_CONCURRENCY", bad)
        assert RefreshConfig.from_env().concurrency == (1 if bad in ("0", "-3") else 6)
    monkeypatch.delenv("JOB_FETCH_CONCURRENCY")
    assert RefreshConfig.from_env().concurrency == 6


def test_budget_fits_vercel_function_window(monkeypatch):
    max_duration = json.loads((ROOT / "vercel.json").read_text())["functions"]["api/index.py"]["maxDuration"]
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("JOB_REFRESH_BUDGET_SECONDS", raising=False)
    cfg = RefreshConfig.from_env()
    assert cfg.company_timeout < cfg.budget < max_duration


# ---- existing adapters & pipeline ----------------------------------------------------------------

def test_existing_adapters_are_used_for_every_source():
    sources = agent_settings.load_sources(AGENT_FIXTURES / "sources.json")
    tasks = agent_main.build_tasks(sources, AsyncFixtureTransport(AGENT_FIXTURES))
    assert {type(adapter) for adapter, _ in tasks} == set(ADAPTERS.values())
    results, _ = run(run_refresh(tasks, tasks[0][0].transport, config()))
    assert {r.source for r in results if r.ok} == {"greenhouse", "lever", "ashby"}


@pytest.fixture
def fixture_env(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("JOB_FETCH_FIXTURES_DIR", str(AGENT_FIXTURES))
    monkeypatch.setenv("JOB_SOURCES_FILE", str(AGENT_FIXTURES / "sources.json"))


def test_refresh_matches_agent_pipeline_exactly(fixture_env):
    """Normalization, location filter, dedupe and sort are the agent's: same jobs, same order."""
    response = client.post("/api/jobs/refresh")
    assert response.status_code == 200
    data = response.json()
    expected = agent_main.run(sources_file=AGENT_FIXTURES / "sources.json", fixtures=AGENT_FIXTURES)
    assert data["jobs"] == expected["jobs"]
    assert data["statistics"] == expected["statistics"]
    ids = [j["id"] for j in data["jobs"]]
    urls = [j["applyUrl"] for j in data["jobs"]]
    assert len(ids) == len(set(ids)) and len(urls) == len(set(urls))  # no duplicates
    stamps = [datetime.fromisoformat((j["updatedAt"] or j["postedAt"]).replace("Z", "+00:00")) for j in data["jobs"]]
    assert stamps == sorted(stamps, reverse=True)
    assert {j["source"] for j in data["jobs"]} == {"greenhouse", "lever", "ashby"}


def test_duplicate_postings_are_removed():
    board = {"jobs": GREENHOUSE_BOARD["jobs"][:2] * 2}  # same postings returned twice
    transport = FakeTransport(script={"anthropic": [board]})
    results, timings = run(run_refresh(greenhouse_tasks(transport, ["anthropic"]), transport, config()))
    output = agent_main.process_results(results, agent_settings.load_location_keywords())
    urls = [j["applyUrl"] for j in output["jobs"]]
    assert len(urls) == len(set(urls)) <= 2


def test_refresh_contract_and_metadata(fixture_env):
    data = client.post("/api/jobs/refresh").json()
    meta = data["refresh"]
    assert {"schemaVersion", "generatedAt", "statistics", "sources", "companies", "failures", "jobs"} <= set(data)
    assert meta["companiesRequested"] == 9
    assert meta["companiesSucceeded"] == 6
    assert meta["companiesFailed"] == 3
    assert meta["jobCount"] == len(data["jobs"]) == 12
    assert meta["concurrency"] == 6 and meta["durationMs"] >= 0
    assert {(f["source"], f["key"]) for f in meta["failures"]} == {
        ("greenhouse", "notion"), ("ashby", "linear"), ("lever", "spotify")} or len(meta["failures"]) == 3
    assert all(set(f) == {"source", "company", "key", "reason"} for f in meta["failures"])
    assert len(meta["slowest"]) <= 5


def test_response_is_gzip_compressed(fixture_env):
    response = client.post("/api/jobs/refresh", headers={"Accept-Encoding": "gzip"})
    assert response.headers.get("content-encoding") == "gzip"


def test_metadata_counts_are_consistent():
    transport = FakeTransport(script={"bad": [HttpError(404, "Not Found")]})
    results, timings = run(run_refresh(greenhouse_tasks(transport, ["ok1", "bad", "ok2"]), transport, config()))
    output = agent_main.process_results(results, ["Remote"])
    meta = refresh_metadata(results, timings, output, duration_ms=12, config=config(concurrency=4))
    assert (meta["companiesRequested"], meta["companiesSucceeded"], meta["companiesFailed"]) == (3, 2, 1)
    assert meta["failures"] == [{"source": "greenhouse", "company": "Bad", "key": "bad", "reason": "HTTP 404"}]
    assert (meta["jobCount"], meta["durationMs"], meta["concurrency"]) == (0, 12, 4)


# ---- failure isolation ---------------------------------------------------------------------------

def test_one_failure_does_not_block_others():
    transport = FakeTransport(script={"b": [HttpError(500, "Server Error")] * 3, "a": [GREENHOUSE_BOARD]})
    results, _ = run(run_refresh(greenhouse_tasks(transport, ["a", "b", "c"]), transport, config()))
    by_key = {r.company.key: r for r in results}
    assert by_key["a"].ok and by_key["a"].jobs and by_key["c"].ok
    assert by_key["b"].error == "HTTP 500"


def test_multiple_partial_failures_still_return_jobs():
    script = {"a": [GREENHOUSE_BOARD], "b": [HttpError(404, "Not Found")], "c": [FetchError("invalid JSON response")],
              "d": [ValueError("boom")]}
    transport = FakeTransport(script=script)
    results, _ = run(run_refresh(greenhouse_tasks(transport, list("abcd")), transport, config()))
    errors = {r.company.key: r.error for r in results}
    assert errors == {"a": None, "b": "HTTP 404", "c": "invalid response", "d": "unexpected error (ValueError)"}
    output = agent_main.process_results(results, agent_settings.load_location_keywords())
    assert output["jobs"]


def test_empty_provider_results_are_success_with_zero_jobs():
    transport = FakeTransport(script={"empty": [{"jobs": []}]})
    results, _ = run(run_refresh(greenhouse_tasks(transport, ["empty"]), transport, config()))
    assert results[0].ok and results[0].jobs == [] and results[0].jobs_fetched == 0


# ---- timeouts & budget ---------------------------------------------------------------------------

def test_per_company_timeout_isolated():
    transport = FakeTransport(delays={"hang": 5}, default_delay=0.01)
    results, _ = run(run_refresh(greenhouse_tasks(transport, ["hang", "a", "b"]), transport,
                                 config(company_timeout=0.1, request_timeout=5)))
    errors = {r.company.key: r.error for r in results}
    assert errors == {"hang": "timeout", "a": None, "b": None}


def test_request_timeout_is_retried_then_reported():
    transport = FakeTransport(delays={"slow": 1})
    result, attempts = run(fetch_company(ADAPTERS["greenhouse"](transport), Company("Slow", "slow"), transport,
                                         config(request_timeout=0.05, retries=1)))
    assert (result.error, attempts, transport.calls["slow"]) == ("timeout", 2, 2)


def test_global_budget_marks_unstarted_companies_not_attempted():
    transport = FakeTransport(default_delay=0.1)
    results, timings = run(run_refresh(greenhouse_tasks(transport, list("abcde")), transport,
                                       config(concurrency=1, budget=0.15)))
    errors = [r.error for r in results]
    assert len(results) == 5
    assert errors[0] is None
    assert errors[-1] == "not attempted (refresh time budget reached)"
    assert "e" not in transport.calls
    assert len(timings) < 5


# ---- retries -------------------------------------------------------------------------------------

def _fetch(transport, key, **cfg):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    result, attempts = run(fetch_company(ADAPTERS["greenhouse"](transport), Company(key.title(), key), transport,
                                         config(**cfg), sleep=fake_sleep, rng=random.Random(1)))
    return result, attempts, sleeps


def test_transient_503_is_retried_then_succeeds():
    transport = FakeTransport(script={"x": [HttpError(503, "Unavailable"), GREENHOUSE_BOARD]})
    result, attempts, sleeps = _fetch(transport, "x", backoff_base=0.5, backoff_cap=4)
    assert result.ok and result.jobs and attempts == 2
    assert len(sleeps) == 1 and 0.25 <= sleeps[0] <= 0.5  # jittered 50-100% of base


@pytest.mark.parametrize("error", [HttpError(429, "Too Many"), HttpError(502, "Bad Gateway"),
                                   TransientError("network error"), TransientError("request timeout")])
def test_transient_errors_retry_with_exponential_backoff(error):
    transport = FakeTransport(script={"x": [error, error, error]})
    result, attempts, sleeps = _fetch(transport, "x", retries=2, backoff_base=0.5, backoff_cap=4)
    assert not result.ok and attempts == 3 and len(sleeps) == 2
    assert 0.25 <= sleeps[0] <= 0.5 and 0.5 <= sleeps[1] <= 1.0


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410])
def test_permanent_4xx_is_not_retried(status):
    transport = FakeTransport(script={"x": [HttpError(status, "Nope"), GREENHOUSE_BOARD]})
    result, attempts, sleeps = _fetch(transport, "x")
    assert result.error == f"HTTP {status}" and attempts == 1 and sleeps == [] and transport.calls["x"] == 1


def test_backoff_is_capped():
    transport = FakeTransport(script={"x": [HttpError(503, "U")] * 6})
    _, attempts, sleeps = _fetch(transport, "x", retries=5, backoff_base=1, backoff_cap=2)
    assert attempts == 6 and max(sleeps) <= 2


# ---- API edge cases ------------------------------------------------------------------------------

def test_all_companies_failed_returns_clean_502(monkeypatch, tmp_path):
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"greenhouse": [{"name": "Nope", "token": "nope", "enabled": True}],
                                   "lever": [{"name": "Gone", "key": "gone", "enabled": True}], "ashby": []}))
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("JOB_FETCH_FIXTURES_DIR", str(AGENT_FIXTURES))
    monkeypatch.setenv("JOB_SOURCES_FILE", str(sources))
    response = client.post("/api/jobs/refresh")
    assert response.status_code == 502
    body = response.json()
    assert body["detail"] == "Could not fetch jobs: all 2 companies failed. Try again later."
    assert body["refresh"]["companiesFailed"] == 2 and "jobs" not in body


def test_no_companies_configured_returns_503(monkeypatch, tmp_path):
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"greenhouse": [{"name": "Off", "token": "off", "enabled": False}],
                                   "lever": [], "ashby": []}))
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("JOB_SOURCES_FILE", str(sources))
    response = client.post("/api/jobs/refresh")
    assert response.status_code == 503
    assert response.json() == {"detail": "No companies are configured for job fetching."}


def test_invalid_config_returns_generic_500(monkeypatch, tmp_path):
    sources = tmp_path / "sources.json"
    sources.write_text("[1, 2]")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("JOB_SOURCES_FILE", str(sources))
    response = client.post("/api/jobs/refresh")
    assert response.status_code == 500
    assert response.json() == {"detail": "Job source configuration is invalid."}
    assert str(tmp_path) not in response.text


def test_refresh_is_post_only():
    assert client.get("/api/jobs/refresh").status_code == 405


def test_dev_overrides_ignored_on_vercel(monkeypatch):
    monkeypatch.setenv("JOB_FETCH_FIXTURES_DIR", str(AGENT_FIXTURES))
    monkeypatch.setenv("VERCEL", "1")
    assert jobs_api._dev_path("JOB_FETCH_FIXTURES_DIR") is None
    monkeypatch.delenv("VERCEL")
    assert jobs_api._dev_path("JOB_FETCH_FIXTURES_DIR") == AGENT_FIXTURES


# ---- security ------------------------------------------------------------------------------------

def test_failure_reasons_expose_no_internals():
    secret = "sk-secret-123"
    cases = [
        HttpError(401, f"Unauthorized {secret}"),
        FetchError("network error: [Errno -2] Name or service not known boards-api.greenhouse.io"),
        FetchError("request timeout after 20s to https://api.lever.co/v0/postings/x"),
        FetchError("invalid JSON response: Expecting value line 1"),
        RuntimeError(f"Traceback ... {secret} /home/user/app/backend/jobs/refresh.py"),
        asyncio.TimeoutError(),
    ]
    reasons = [safe_reason(e) for e in cases]
    assert reasons == ["HTTP 401", "network error", "timeout", "invalid response",
                       "unexpected error (RuntimeError)", "timeout"]
    assert not any(secret in r or "/home" in r or "http" in r.lower().replace("http 401", "") for r in reasons)


def test_refresh_response_contains_no_env_secrets(fixture_env, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gm-secret-value")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-secret-value")
    text = client.post("/api/jobs/refresh").text
    assert "secret-value" not in text and str(AGENT_FIXTURES) not in text and "Traceback" not in text


# ---- frontend no longer fans out -----------------------------------------------------------------

def test_frontend_makes_no_direct_provider_calls():
    offenders = []
    for path in (ROOT / "src").rglob("*"):
        if path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
            text = path.read_text(encoding="utf-8")
            if re.search(r"greenhouse\.io|lever\.co|ashbyhq\.com", text):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
    service = (ROOT / "src" / "services" / "jobRefreshService.js").read_text()
    assert "'/api/jobs/refresh'" in service and "method: 'POST'" in service
    assert not (ROOT / "src" / "services" / "greenhouseService.js").exists()


# ---- /api/companies (Node function) still works --------------------------------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_api_companies_node_function_still_works():
    script = """
      const { default: handler } = await import('./api/companies.js');
      let status = 200, body;
      const res = { status(c) { status = c; return this; }, json(b) { body = b; return this; },
                    setHeader() { return this; } };
      await handler({ method: 'GET' }, res);
      console.log(JSON.stringify({ status, body }));
    """
    env = {"PATH": subprocess.os.environ["PATH"],
           "GREENHOUSE_COMPANIES": json.dumps([{"name": "Anthropic", "token": "anthropic", "enabled": True}])}
    out = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout.strip().splitlines()[-1])
    assert result["status"] == 200
    assert "Anthropic" in json.dumps(result["body"])
