"""POST /api/jobs/refresh — the only job-fetching call the browser makes."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from agent.config import settings as agent_settings
from agent.main import build_tasks, process_results

from ..config import on_vercel
from ..jobs.refresh import AsyncFixtureTransport, AsyncHttpTransport, RefreshConfig, refresh_metadata, run_refresh

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
log = logging.getLogger("backend.jobs")


def _dev_path(name: str):
    """Local development/tests only (ignored on Vercel)."""
    value = os.environ.get(name)
    return Path(value) if value and not on_vercel() else None


@router.post("/refresh")
async def refresh_jobs():
    """Fetch every enabled company server-side (Greenhouse, Lever, Ashby), run the
    shared pipeline and return Common Jobs plus refresh metadata."""
    started = time.monotonic()
    config = RefreshConfig.from_env()
    try:
        sources = agent_settings.load_sources(_dev_path("JOB_SOURCES_FILE"))
        location_keywords = agent_settings.load_location_keywords()
    except (OSError, ValueError) as error:
        log.error("Job source configuration error: %s", type(error).__name__)
        return JSONResponse(status_code=500, content={"detail": "Job source configuration is invalid."})

    fixtures = _dev_path("JOB_FETCH_FIXTURES_DIR")
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(config.request_timeout, connect=min(5.0, config.request_timeout)),
        limits=httpx.Limits(max_connections=config.concurrency, max_keepalive_connections=config.concurrency),
        follow_redirects=True,
    ) as client:
        transport = AsyncFixtureTransport(fixtures) if fixtures else AsyncHttpTransport(client)
        tasks = build_tasks(sources, transport)
        if not tasks:
            return JSONResponse(status_code=503, content={"detail": "No companies are configured for job fetching."})
        results, timings = await run_refresh(tasks, transport, config)

    output = process_results(results, location_keywords)
    meta = refresh_metadata(results, timings, output, duration_ms=int((time.monotonic() - started) * 1000), config=config)
    output["refresh"] = meta
    log.info("jobs refresh: %d/%d companies ok, %d jobs, %d ms (concurrency %d)",
             meta["companiesSucceeded"], meta["companiesRequested"], meta["jobCount"], meta["durationMs"], meta["concurrency"])

    if meta["companiesSucceeded"] == 0:
        return JSONResponse(status_code=502, content={
            "detail": f"Could not fetch jobs: all {meta['companiesRequested']} companies failed. Try again later.",
            "refresh": meta,
        })
    return output
