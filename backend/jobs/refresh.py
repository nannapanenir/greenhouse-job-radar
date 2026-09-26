"""Job Refresh Manager: server-side provider fetching for POST /api/jobs/refresh.

Reuses the Phase 1 agent — adapters (URLs, response parsing, Common Job
mapping via ``JobAdapter.process_payload``) and the shared pipeline
(``agent.main.process_results``: normalize -> filter -> dedupe -> sort). Only
the transport is new: async httpx with

* a **bounded worker queue**: N workers (``JOB_FETCH_CONCURRENCY``, default 6)
  pull companies from one queue, so at most N requests are in flight and the
  next company starts the moment any slot frees (no fixed batches);
* per-request and per-company **timeouts**;
* limited **retries** with exponential backoff + jitter for transient errors
  only (timeouts, network errors, 429, 5xx) — never for other 4xx;
* a total **refresh budget** so the request finishes inside the serverless
  execution window; companies that can't run in time are reported, not hung on;
* **failure isolation**: a failed company is recorded with a sanitized reason
  and never fails the refresh.

Triggered only by the user's Fetch button — no scheduling, caching or storage.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import httpx

from agent.adapters.base import USER_AGENT, Company, CompanyResult, FetchError, FixtureTransport, HttpError, JobAdapter

from ..config import on_vercel

log = logging.getLogger("backend.jobs")


def _float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, ""))
        return value if value > 0 else default
    except ValueError:
        return default


@dataclass(frozen=True)
class RefreshConfig:
    concurrency: int = 6
    request_timeout: float = 15.0      # one HTTP request
    company_timeout: float = 25.0      # all attempts for one company
    retries: int = 2                   # extra attempts for transient failures
    backoff_base: float = 0.5
    backoff_cap: float = 4.0
    budget: float = 120.0              # whole refresh

    @classmethod
    def from_env(cls) -> "RefreshConfig":
        try:
            concurrency = max(1, int(os.environ.get("JOB_FETCH_CONCURRENCY", "6")))
        except ValueError:
            concurrency = 6
        try:
            retries = max(0, int(os.environ.get("JOB_FETCH_RETRIES", "2")))
        except ValueError:
            retries = 2
        return cls(
            concurrency=concurrency,
            request_timeout=_float_env("JOB_FETCH_TIMEOUT_SECONDS", 15.0),
            company_timeout=_float_env("JOB_FETCH_COMPANY_TIMEOUT_SECONDS", 25.0),
            retries=retries,
            # Vercel function maxDuration is 60s (vercel.json); leave room for processing + response.
            budget=_float_env("JOB_REFRESH_BUDGET_SECONDS", 45.0 if on_vercel() else 120.0),
        )


class TransientError(FetchError):
    """A failure worth retrying (timeout, network error, 429/5xx)."""


def _is_transient(error: Exception) -> bool:
    if isinstance(error, HttpError):
        return error.status == 429 or error.status >= 500
    return isinstance(error, TransientError)


def safe_reason(error: Exception) -> str:
    """Short, non-sensitive failure reason for the UI/API (no stack traces, hosts or internals)."""
    if isinstance(error, HttpError):
        return f"HTTP {error.status}"
    if isinstance(error, asyncio.TimeoutError):
        return "timeout"
    if isinstance(error, FetchError):
        text = str(error)
        for prefix, label in (("request timeout", "timeout"), ("network error", "network error"),
                              ("invalid JSON", "invalid response"), ("unexpected", "unexpected response")):
            if text.startswith(prefix):
                return label
        return text[:120]  # provider-reported board error, e.g. Lever "Document not found"
    return f"unexpected error ({type(error).__name__})"


class AsyncHttpTransport:
    """Async JSON GET with a shared connection pool."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def get_json(self, url: str, *, source: str, company_key: str) -> Any:
        try:
            response = await self.client.get(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        except httpx.TimeoutException:
            raise TransientError("request timeout") from None
        except httpx.HTTPError:
            raise TransientError("network error") from None
        if response.status_code >= 400:
            raise HttpError(response.status_code, response.reason_phrase or "Error")
        try:
            return response.json()
        except ValueError:
            raise FetchError("invalid JSON response") from None


class AsyncFixtureTransport:
    """Dev/test only: serves saved responses (tests/agent/fixtures layout)."""

    def __init__(self, root: Path, delay: float = 0.0):
        self.inner = FixtureTransport(root)
        self.delay = delay

    async def get_json(self, url: str, *, source: str, company_key: str) -> Any:
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.inner.get_json(url, source=source, company_key=company_key)


@dataclass
class CompanyTiming:
    source: str
    company: str
    key: str
    duration_ms: int
    attempts: int


async def fetch_company(
    adapter: JobAdapter,
    company: Company,
    transport,
    config: RefreshConfig,
    *,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    rng: random.Random = random.Random(),
) -> tuple[CompanyResult, int]:
    """Fetch one board with retries; returns (result, attempts). Never raises."""
    url = adapter.board_url(company)
    attempts = 0
    while True:
        attempts += 1
        try:
            payload = await asyncio.wait_for(
                transport.get_json(url, source=adapter.source, company_key=company.key), config.request_timeout
            )
            return adapter.process_payload(company, payload), attempts
        except Exception as error:  # noqa: BLE001 - every failure is isolated per company
            transient = isinstance(error, asyncio.TimeoutError) or _is_transient(error)
            if transient and attempts <= config.retries:
                delay = min(config.backoff_cap, config.backoff_base * 2 ** (attempts - 1))
                await sleep(delay * (0.5 + rng.random() / 2))  # jitter: 50-100% of the backoff
                continue
            reason = safe_reason(error)
            log.warning("%s/%s: failed after %d attempt(s): %s", adapter.source, company.key, attempts, reason)
            return CompanyResult(source=adapter.source, company=company, error=reason), attempts


async def run_refresh(
    tasks: list[tuple[JobAdapter, Company]],
    transport,
    config: RefreshConfig,
    *,
    clock: Callable[[], float] = time.monotonic,
    on_start: Optional[Callable[[Company], None]] = None,
) -> tuple[list[CompanyResult], list[CompanyTiming]]:
    """Bounded worker queue over all companies. Results keep task (config) order."""
    results: list[Optional[CompanyResult]] = [None] * len(tasks)
    timings: list[Optional[CompanyTiming]] = [None] * len(tasks)
    queue: asyncio.Queue[int] = asyncio.Queue()
    for index in range(len(tasks)):
        queue.put_nowait(index)
    deadline = clock() + config.budget

    async def worker() -> None:
        while True:
            try:
                index = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            adapter, company = tasks[index]
            remaining = deadline - clock()
            if remaining <= 0:
                results[index] = CompanyResult(source=adapter.source, company=company,
                                               error="not attempted (refresh time budget reached)")
                continue
            if on_start:
                on_start(company)
            started = clock()
            attempts = 0
            try:
                result, attempts = await asyncio.wait_for(
                    fetch_company(adapter, company, transport, config), min(config.company_timeout, remaining)
                )
            except asyncio.TimeoutError:
                result = CompanyResult(source=adapter.source, company=company, error="timeout")
                log.warning("%s/%s: timed out", adapter.source, company.key)
            results[index] = result
            timings[index] = CompanyTiming(adapter.source, company.name, company.key,
                                           int((clock() - started) * 1000), attempts)

    workers = [asyncio.create_task(worker()) for _ in range(min(config.concurrency, len(tasks)))]
    await asyncio.gather(*workers)
    return [r for r in results if r is not None], [t for t in timings if t is not None]


def refresh_metadata(results: list[CompanyResult], timings: list[CompanyTiming], output: dict,
                     *, duration_ms: int, config: RefreshConfig) -> dict:
    succeeded = [r for r in results if r.ok]
    return {
        "companiesRequested": len(results),
        "companiesSucceeded": len(succeeded),
        "companiesFailed": len(results) - len(succeeded),
        "jobCount": len(output["jobs"]),
        "jobsScanned": output["statistics"]["jobsScanned"],
        "durationMs": duration_ms,
        "concurrency": config.concurrency,
        "failures": [{"source": r.source, "company": r.company.name, "key": r.company.key, "reason": r.error}
                     for r in results if not r.ok],
        "slowest": [{"source": t.source, "company": t.company, "key": t.key, "durationMs": t.duration_ms,
                     "attempts": t.attempts}
                    for t in sorted(timings, key=lambda t: t.duration_ms, reverse=True)[:5]],
    }
