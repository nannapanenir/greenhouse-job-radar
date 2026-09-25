"""Vercel Python Function entry point for the Job Radar API.

Exposes the existing FastAPI application (``backend.main:app``) — there is no
second backend. vercel.json rewrites /api/health, /api/ai/* and /api/resume/*
here; /api/companies stays the Node function in api/companies.js.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.main import app  # noqa: E402,F401  (ASGI app picked up by Vercel)
