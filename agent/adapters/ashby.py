"""Ashby adapter.

Public job board API (no auth):
    GET https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=false
Response: ``{"jobs": [...]}``. Unlisted postings (``isListed == false``) are
skipped. Parsing is defensive and must be confirmed live (see agent/README.md).
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from ..models.job import Job
from ..processing.normalizer import clean_html_content, text_or_none
from .base import Company, FetchError, JobAdapter


def _secondary_locations(raw: dict) -> list[str]:
    names = []
    for item in raw.get("secondaryLocations") or []:
        name = item.get("location") if isinstance(item, dict) else item
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _country(raw: dict) -> Optional[str]:
    address = raw.get("address")
    if isinstance(address, dict) and isinstance(address.get("postalAddress"), dict):
        return text_or_none(address["postalAddress"].get("addressCountry"))
    return None


class AshbyAdapter(JobAdapter):
    source = "ashby"

    def board_url(self, company: Company) -> str:
        return (
            "https://api.ashbyhq.com/posting-api/job-board/"
            f"{quote(company.key, safe='')}?includeCompensation=false"
        )

    def extract_postings(self, payload: Any) -> list[dict]:
        if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
            return payload["jobs"]
        raise FetchError("unexpected Ashby response shape")

    def map_job(self, raw: dict, company: Company) -> Optional[Job]:
        if not raw.get("id") or raw.get("isListed") is False:
            return None

        metadata = {
            key: value
            for key, value in {
                "isRemote": raw.get("isRemote"),
                "workplaceType": raw.get("workplaceType"),
                "employmentType": raw.get("employmentType"),
                "department": raw.get("department"),
                "team": raw.get("team"),
                "secondaryLocations": _secondary_locations(raw),
                "country": _country(raw),
            }.items()
            if value not in (None, "", [])
        }

        description = text_or_none(raw.get("descriptionPlain")) or clean_html_content(raw.get("descriptionHtml"))

        return Job(
            source=self.source,
            source_job_id=str(raw["id"]),
            company=company.name,
            company_key=company.key,
            title=text_or_none(raw.get("title")),
            location=text_or_none(raw.get("location")),
            description=description.strip() if description else None,
            posted_at=text_or_none(raw.get("publishedAt")),
            updated_at=text_or_none(raw.get("updatedAt")),  # only if Ashby provides it
            apply_url=text_or_none(raw.get("applyUrl")) or text_or_none(raw.get("jobUrl")),
            source_url=text_or_none(raw.get("jobUrl")),
            metadata=metadata,
        )
