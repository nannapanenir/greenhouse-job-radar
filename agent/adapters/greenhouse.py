"""Greenhouse adapter.

Same endpoint and field mapping as the existing frontend
(``src/services/greenhouseService.js``):
    GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from ..models.job import Job
from ..processing.normalizer import clean_html_content, text_or_none
from .base import Company, JobAdapter


def _location(raw: dict) -> Optional[str]:
    location = raw.get("location")
    if isinstance(location, dict):
        return text_or_none(location.get("name"))
    return text_or_none(location)


class GreenhouseAdapter(JobAdapter):
    source = "greenhouse"

    def board_url(self, company: Company) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{quote(company.key, safe='')}/jobs?content=true"

    def extract_postings(self, payload: Any) -> list[dict]:
        # Existing flow: `data.jobs || []`
        if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
            return payload["jobs"]
        return []

    def map_job(self, raw: dict, company: Company) -> Optional[Job]:
        if raw.get("id") is None:
            return None

        metadata = {}
        for raw_key, meta_key in (("internal_job_id", "internalJobId"), ("requisition_id", "requisitionId")):
            if raw.get(raw_key) is not None:
                metadata[meta_key] = raw[raw_key]
        departments = [d.get("name") for d in raw.get("departments") or [] if isinstance(d, dict) and d.get("name")]
        if departments:
            metadata["departments"] = departments

        return Job(
            source=self.source,
            source_job_id=str(raw["id"]),
            company=company.name,
            company_key=company.key,
            title=text_or_none(raw.get("title")),
            location=_location(raw),
            description=clean_html_content(raw.get("content")),
            posted_at=text_or_none(raw.get("first_published")),
            updated_at=text_or_none(raw.get("updated_at")),
            apply_url=text_or_none(raw.get("absolute_url")),
            source_url=text_or_none(raw.get("absolute_url")),
            metadata=metadata,
        )
