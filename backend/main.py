"""Job Radar Python API.

    uvicorn backend.main:app --reload --port 8000        # from the repo root
    python -m backend                                     # same, via __main__

The Vite dev server proxies /api/health, /api/ai, /api/resume and /api/jobs
here (see vite.config.js); /api/companies stays a Vercel Node function.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import resume, system

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Job Radar API", version=system.API_VERSION)
app.include_router(system.router)
app.include_router(resume.router)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("backend").exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})
