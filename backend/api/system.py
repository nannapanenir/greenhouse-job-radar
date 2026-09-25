"""Health, AI status/settings and Phase 1 job data."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config
from ..config import REPO_ROOT, SettingsError

router = APIRouter()

API_VERSION = "2.0.0"
JOBS_FILE = REPO_ROOT / "public" / "data" / "jobs.json"


@router.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": API_VERSION, "aiConfigured": config.load_ai_settings().configured}


@router.get("/api/ai/status")
def ai_status() -> dict:
    """Provider configuration status. Never returns the API key."""
    return config.load_ai_settings().public_status()


class AISettingsBody(BaseModel):
    provider: str = "openrouter"
    model: str = ""
    apiKey: str = ""
    baseUrl: str = ""


@router.post("/api/ai/settings")
def save_ai_settings(body: AISettingsBody) -> dict:
    try:
        settings = config.save_ai_settings(body.provider, body.model, body.apiKey, body.baseUrl)
    except SettingsError as error:
        raise HTTPException(status_code=409 if config.env_managed() else 400, detail=str(error)) from None
    return settings.public_status()


@router.delete("/api/ai/settings")
def clear_ai_settings() -> dict:
    try:
        return config.clear_ai_settings().public_status()
    except SettingsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.get("/api/jobs")
def jobs() -> dict:
    """The Phase 1 agent's latest output (run `python agent/main.py`)."""
    try:
        return json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No jobs collected yet. Run: python agent/main.py") from None
