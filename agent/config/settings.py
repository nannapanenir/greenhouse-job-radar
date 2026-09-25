"""Agent settings and source loading.

Company lists:
  greenhouse -> reuses the EXISTING app config, so there is one list:
                GREENHOUSE_COMPANIES env var (same JSON as on Vercel), else
                src/config/greenhouse-companies.json. A "greenhouse" key in
                sources.json overrides both (used for fixtures/tests).
  lever, ashby -> agent/config/sources.json

Location keywords come from src/config/role-profiles.json, the same list the
React app uses.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from ..adapters.base import Company
from ..models.job import SOURCES

log = logging.getLogger("agent")

AGENT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = AGENT_DIR.parent

DEFAULT_SOURCES_FILE = AGENT_DIR / "config" / "sources.json"
DEFAULT_OUTPUT_FILE = REPO_ROOT / "public" / "data" / "jobs.json"
GREENHOUSE_CONFIG_FILE = REPO_ROOT / "src" / "config" / "greenhouse-companies.json"
ROLE_PROFILES_FILE = REPO_ROOT / "src" / "config" / "role-profiles.json"

REQUEST_TIMEOUT_SECONDS = 20.0
MAX_WORKERS = 8


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_companies(entries: Any, origin: str) -> list[Company]:
    """Validate company entries (same rules as api/companies.js).

    Each entry needs a non-empty ``name``, a non-empty ``key`` (``token`` is
    accepted for the existing Greenhouse format) and a boolean ``enabled``.
    Invalid entries are skipped with a warning.
    """
    if not isinstance(entries, list):
        raise ValueError(f"{origin}: expected a JSON array of companies")

    companies = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            log.warning("%s[%d]: not an object, skipped", origin, index)
            continue
        name = entry.get("name")
        key = entry.get("key", entry.get("token"))
        enabled = entry.get("enabled")
        if not (isinstance(name, str) and name.strip() and isinstance(key, str) and key.strip()
                and isinstance(enabled, bool)):
            log.warning("%s[%d]: invalid company entry, skipped", origin, index)
            continue
        companies.append(Company(name=name.strip(), key=key.strip(), enabled=enabled))
    return companies


def _existing_greenhouse_companies() -> list[Company]:
    raw_env = os.environ.get("GREENHOUSE_COMPANIES")
    if raw_env:
        return parse_companies(json.loads(raw_env), "GREENHOUSE_COMPANIES")
    return parse_companies(_read_json(GREENHOUSE_CONFIG_FILE), str(GREENHOUSE_CONFIG_FILE.relative_to(REPO_ROOT)))


def load_sources(sources_file: Optional[Path] = None) -> dict[str, list[Company]]:
    """Return {source: [Company]} for every provider (enabled and disabled)."""
    path = Path(sources_file) if sources_file else DEFAULT_SOURCES_FILE
    config = _read_json(path) if path.is_file() else {}
    if not isinstance(config, dict):
        raise ValueError(f"{path}: expected a JSON object")

    unknown = sorted(set(config) - set(SOURCES) - {"$comment"})
    if unknown:
        log.warning("%s: unknown sources ignored: %s", path.name, ", ".join(unknown))

    sources: dict[str, list[Company]] = {}
    for source in SOURCES:
        if source == "greenhouse" and "greenhouse" not in config:
            sources[source] = _existing_greenhouse_companies()
        else:
            sources[source] = parse_companies(config.get(source, []), f"{path.name}:{source}")
    return sources


def load_location_keywords(path: Path = ROLE_PROFILES_FILE) -> list[str]:
    keywords = _read_json(path).get("locationKeywords")
    if not isinstance(keywords, list) or not keywords:
        raise ValueError(f"{path}: missing locationKeywords")
    return [kw for kw in keywords if isinstance(kw, str)]
