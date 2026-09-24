"""Universal (not user-specific) filters.

Only the US location filter runs in the agent, matching what the existing
Greenhouse flow applies at fetch time. Role profiles, search, time and status
filters stay in the React app because they are per-user.

``build_keyword_regex`` is a port of ``buildKeywordRegex`` in
``src/utils/jobFilters.js`` (whole word, case-insensitive).
"""

from __future__ import annotations

import re
from typing import Iterable

from ..models.job import Job

# JS escapeRegExp character class: [.*+?^${}()|[\]\\]
_REGEX_SPECIAL = re.compile(r"([.*+?^${}()|\[\]\\])")


def build_keyword_regex(keyword: str) -> re.Pattern[str]:
    pattern = _REGEX_SPECIAL.sub(r"\\\1", keyword.strip())
    pattern = re.sub(r"\s+", lambda _: r"\s+", pattern)
    return re.compile(rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])", re.IGNORECASE)


def compile_keywords(keywords: Iterable[str]) -> list[re.Pattern[str]]:
    return [
        build_keyword_regex(kw)
        for kw in keywords
        if isinstance(kw, str) and kw.strip() != ""
    ]


def matches_location(location: str | None, compiled: list[re.Pattern[str]]) -> bool:
    if not location:
        return False
    return any(regex.search(location) for regex in compiled)


def is_us_job(job: Job, compiled: list[re.Pattern[str]]) -> bool:
    """Keep jobs with a US location, and jobs with no location (may be remote)."""
    return job.location is None or matches_location(job.location, compiled)


def filter_jobs(jobs: list[Job], location_keywords: Iterable[str]) -> list[Job]:
    compiled = compile_keywords(location_keywords)
    return [job for job in jobs if is_us_job(job, compiled)]
