"""Newest-first sorting.

Timestamp meaning differs by provider (see agent/README.md):
  greenhouse -> updated_at (last update)
  lever      -> posted_at only (createdAt; Lever exposes no update time)
  ashby      -> posted_at only (publishedAt)

The sort key is ``updated_at`` falling back to ``posted_at``. Jobs with no
usable timestamp go last. The sort is stable, so ties keep input order.
"""

from __future__ import annotations

from datetime import datetime

from ..models.job import Job
from .normalizer import parse_timestamp


def job_timestamp(job: Job) -> datetime | None:
    return parse_timestamp(job.updated_at) or parse_timestamp(job.posted_at)


def sort_jobs(jobs: list[Job]) -> list[Job]:
    dated = [job for job in jobs if job_timestamp(job) is not None]
    undated = [job for job in jobs if job_timestamp(job) is None]
    dated.sort(key=job_timestamp, reverse=True)
    return dated + undated
