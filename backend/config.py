"""AI provider settings. Secrets never leave the server.

Precedence: environment variables > local settings file.

Environment (e.g. Vercel project settings or a shell export):
    AI_PROVIDER          openrouter | local | gemini
    AI_MODEL             model name, e.g. openai/gpt-4o-mini, llama3.2:3b, gemini-2.0-flash
    OPENROUTER_API_KEY   for provider=openrouter
    GEMINI_API_KEY       for provider=gemini
    LOCAL_AI_BASE_URL    for provider=local, e.g. http://localhost:11434/v1
    LOCAL_AI_API_KEY     optional, for local servers that require one

Local settings file (written from the Resume AI Settings screen, like the
standalone app's resume-tailor-data/settings.json): backend/data/settings.json
with 0600 permissions. Override its folder with RESUME_AI_DATA_DIR.
Local development only: on Vercel (VERCEL=1) the file is never read or
written — configuration comes exclusively from the project's environment
variables and the settings endpoints are read-only.

AI time budget (keeps retries inside the serverless execution window):
    AI_REQUEST_TIMEOUT_SECONDS   per attempt   (default 45 locally, 25 on Vercel)
    AI_TOTAL_BUDGET_SECONDS      all attempts  (default 150 locally, 50 on Vercel;
                                               Vercel maxDuration is 60 in vercel.json)
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = ("openrouter", "local", "gemini")


def data_dir() -> Path:
    return Path(os.environ.get("RESUME_AI_DATA_DIR") or REPO_ROOT / "backend" / "data")


def settings_file() -> Path:
    return data_dir() / "settings.json"


@dataclass(frozen=True)
class AISettings:
    provider: str = "openrouter"
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    source: str = "none"  # env | file | none

    @property
    def configured(self) -> bool:
        if not self.model:
            return False
        if self.provider == "local":
            return bool(self.base_url)
        return bool(self.api_key)

    def public_status(self) -> dict:
        """Safe to send to the browser: never includes the key."""
        return {
            "configured": self.configured,
            "provider": self.provider,
            "model": self.model,
            "baseUrl": self.base_url if self.provider == "local" else None,
            "hasApiKey": bool(self.api_key),
            "source": self.source,
            "editable": not env_managed(),
            "managedBy": "vercel" if on_vercel() else ("environment" if env_managed() else None),
            "providers": list(PROVIDERS),
        }


def on_vercel() -> bool:
    """Vercel sets VERCEL=1 in its build and runtime environments."""
    return os.environ.get("VERCEL") == "1"


def env_managed() -> bool:
    """True when AI settings come only from environment variables (read-only)."""
    return on_vercel() or bool(os.environ.get("AI_PROVIDER") or os.environ.get("AI_MODEL"))


def _float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, ""))
        return value if value > 0 else default
    except ValueError:
        return default


def ai_timeouts() -> tuple[float, float]:
    """(per-attempt timeout, total budget) in seconds for AI calls."""
    if on_vercel():
        return _float_env("AI_REQUEST_TIMEOUT_SECONDS", 25.0), _float_env("AI_TOTAL_BUDGET_SECONDS", 50.0)
    return _float_env("AI_REQUEST_TIMEOUT_SECONDS", 45.0), _float_env("AI_TOTAL_BUDGET_SECONDS", 150.0)


def _from_env() -> AISettings:
    provider = (os.environ.get("AI_PROVIDER") or "openrouter").strip().lower()
    if provider not in PROVIDERS:
        provider = "openrouter"
    key_var = {"openrouter": "OPENROUTER_API_KEY", "gemini": "GEMINI_API_KEY", "local": "LOCAL_AI_API_KEY"}[provider]
    return AISettings(
        provider=provider,
        model=(os.environ.get("AI_MODEL") or "").strip() or None,
        api_key=(os.environ.get(key_var) or "").strip() or None,
        base_url=((os.environ.get("LOCAL_AI_BASE_URL") or "").strip() or None) if provider == "local" else None,
        source="env",
    )


def _from_file() -> AISettings:
    path = settings_file()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AISettings()
    provider = raw.get("provider") if raw.get("provider") in PROVIDERS else "openrouter"
    return AISettings(
        provider=provider,
        model=raw.get("model") or None,
        api_key=raw.get("apiKey") or None,
        base_url=raw.get("baseUrl") or None,
        source="file" if raw.get("model") else "none",
    )


def load_ai_settings() -> AISettings:
    return _from_env() if env_managed() else _from_file()


class SettingsError(ValueError):
    pass


def save_ai_settings(provider: str, model: str, api_key: str = "", base_url: str = "") -> AISettings:
    """Same rules as the standalone POST /api/settings."""
    if env_managed():
        raise SettingsError(_READ_ONLY_MESSAGE())
    provider = provider if provider in PROVIDERS else "openrouter"
    model = (model or "").strip()
    api_key = (api_key or "").strip()
    base_url = (base_url or "").strip()
    if not model:
        raise SettingsError("A model name is required.")

    existing = _from_file()
    if provider == "local":
        if not base_url:
            raise SettingsError("A local server URL is required (e.g. http://localhost:11434/v1).")
        data = {"provider": provider, "model": model, "baseUrl": base_url, "apiKey": api_key or None}
    else:
        # Blank key = keep the stored one (e.g. only changing the model).
        key = api_key or (existing.api_key if existing.provider == provider else "") or ""
        if not key:
            raise SettingsError("An API key is required.")
        data = {"provider": provider, "model": model, "apiKey": key, "baseUrl": None}

    _write_private_json(settings_file(), data)
    return load_ai_settings()


def clear_ai_settings() -> AISettings:
    if env_managed():
        raise SettingsError(_READ_ONLY_MESSAGE())
    try:
        settings_file().unlink()
    except FileNotFoundError:
        pass
    return load_ai_settings()


def _READ_ONLY_MESSAGE() -> str:  # noqa: N802 - constant-like helper
    if on_vercel():
        return ("AI settings are managed by Vercel environment variables (AI_PROVIDER, AI_MODEL and the provider key). "
                "Change them in the Vercel project settings and redeploy.")
    return "AI settings are managed by server environment variables (AI_PROVIDER / AI_MODEL)."


def _write_private_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".settings-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.chmod(tmp, 0o600)  # holds an API key: owner-only
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
