"""Builds and writes public/data/jobs.json."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..adapters.base import CompanyResult
from ..models.job import SOURCES, Job

SCHEMA_VERSION = 1


def build_output(
    jobs: list[Job],
    results: list[CompanyResult],
    *,
    jobs_after_filters: int,
    generated_at: Optional[str] = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    per_source = {
        source: {"companies": 0, "successful": 0, "failures": 0, "jobsScanned": 0, "jobs": 0}
        for source in SOURCES
    }
    for result in results:
        stats = per_source[result.source]
        stats["companies"] += 1
        stats["successful" if result.ok else "failures"] += 1
        stats["jobsScanned"] += result.jobs_fetched
    for job in jobs:
        per_source[job.source]["jobs"] += 1

    successful = sum(1 for r in results if r.ok)
    jobs_scanned = sum(r.jobs_fetched for r in results)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "statistics": {
            "companiesSearched": len(results),
            "successfulCompanies": successful,
            "failedCompanies": len(results) - successful,
            "jobsScanned": jobs_scanned,
            "jobsAfterFilters": jobs_after_filters,
            "duplicatesRemoved": jobs_after_filters - len(jobs),
            "jobsKept": len(jobs),
        },
        "sources": per_source,
        "companies": [
            {
                "source": r.source,
                "name": r.company.name,
                "key": r.company.key,
                "status": "ok" if r.ok else "failed",
                "jobsFetched": r.jobs_fetched,
                "jobsKept": r.jobs_kept,
                **({"error": r.error} if r.error else {}),
            }
            for r in results
        ],
        "failures": [
            {"source": r.source, "company": r.company.name, "key": r.company.key, "error": r.error}
            for r in results
            if not r.ok
        ],
        "jobs": [job.to_dict() for job in jobs],
    }


def write_json(data: dict[str, Any], path: Path) -> None:
    """Atomic write: a failed run never leaves a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".jobs-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(tmp_name, 0o644)  # mkstemp creates 0600; the file is served publicly
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
