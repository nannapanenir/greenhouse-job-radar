"""Provider-independent deduplication (exact identity only, no fuzzy matching).

A job is a duplicate if its apply URL or its global id was already seen.
The first occurrence wins, so input order (source, then company config
order) decides which copy is kept — same as the existing Greenhouse flow.
"""

from __future__ import annotations

from ..models.job import Job


def deduplicate_jobs(jobs: list[Job]) -> list[Job]:
    seen_urls: set[str] = set()
    seen_ids: set[str] = set()
    unique: list[Job] = []

    for job in jobs:
        if (job.apply_url and job.apply_url in seen_urls) or job.id in seen_ids:
            continue
        if job.apply_url:
            seen_urls.add(job.apply_url)
        seen_ids.add(job.id)
        unique.append(job)

    return unique
