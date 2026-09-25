"""Lever adapter.

Public postings API (no auth):
    GET https://api.lever.co/v0/postings/{site}?mode=json
Response: a JSON array of postings. Field names follow Lever's public
postings API docs; parsing is defensive and must be confirmed live
(see agent/README.md).
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from ..models.job import Job
from ..processing.normalizer import clean_html_content, epoch_ms_to_iso, text_or_none
from .base import Company, FetchError, JobAdapter


def _description(raw: dict) -> str:
    parts: list[str] = []

    intro = text_or_none(raw.get("descriptionPlain")) or clean_html_content(raw.get("description"))
    if intro:
        parts.append(intro.strip())

    for item in raw.get("lists") or []:
        if not isinstance(item, dict):
            continue
        heading = text_or_none(item.get("text"))
        body = clean_html_content(item.get("content"))
        section = "\n".join(p for p in (heading, body) if p)
        if section:
            parts.append(section)

    closing = text_or_none(raw.get("additionalPlain")) or clean_html_content(raw.get("additional"))
    if closing:
        parts.append(closing.strip())

    return "\n\n".join(parts)


class LeverAdapter(JobAdapter):
    source = "lever"

    def board_url(self, company: Company) -> str:
        return f"https://api.lever.co/v0/postings/{quote(company.key, safe='')}?mode=json"

    def extract_postings(self, payload: Any) -> list[dict]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and payload.get("ok") is False:
            raise FetchError(str(payload.get("error") or "Lever returned an error"))
        raise FetchError("unexpected Lever response shape")

    def map_job(self, raw: dict, company: Company) -> Optional[Job]:
        if not raw.get("id"):
            return None

        categories = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
        metadata = {
            key: value
            for key, value in {
                "team": categories.get("team"),
                "department": categories.get("department"),
                "commitment": categories.get("commitment"),
                "allLocations": categories.get("allLocations"),
                "workplaceType": raw.get("workplaceType"),
                "country": raw.get("country"),
            }.items()
            if value not in (None, "", [])
        }

        return Job(
            source=self.source,
            source_job_id=str(raw["id"]),
            company=company.name,
            company_key=company.key,
            title=text_or_none(raw.get("text")),
            location=text_or_none(categories.get("location")),
            description=_description(raw),
            posted_at=epoch_ms_to_iso(raw.get("createdAt")),
            updated_at=None,  # Lever's public API has no "updated" timestamp
            apply_url=text_or_none(raw.get("applyUrl")) or text_or_none(raw.get("hostedUrl")),
            source_url=text_or_none(raw.get("hostedUrl")),
            metadata=metadata,
        )
