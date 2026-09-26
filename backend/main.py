"""Job Radar Python API.

    uvicorn backend.main:app --reload --port 8000        # from the repo root
    python -m backend                                     # same, via __main__

The Vite dev server proxies /api/health, /api/ai, /api/resume and /api/jobs
here (see vite.config.js); /api/companies stays a Vercel Node function.
POST /api/jobs/refresh fetches all job providers server-side (backend/jobs/refresh.py).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .api import jobs, resume, system

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Job Radar API", version=system.API_VERSION)
app.include_router(system.router)
app.include_router(resume.router)
app.include_router(jobs.router)
# Job refresh responses carry many descriptions; compress them (smaller transfer, and
# keeps the response well under Vercel's function response size limit).
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("backend").exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})
