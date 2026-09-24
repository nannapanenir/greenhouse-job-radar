"""Provider-independent Job model.

Every adapter returns this shape. Field names are snake_case in Python and
camelCase in the exported JSON (see ``Job.to_dict``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

SOURCES = ("greenhouse", "lever", "ashby")


def build_job_id(source: str, company_key: str, source_job_id: str) -> str:
    """Globally unique id: ``source:companyKey:sourceJobId``."""
    return f"{source}:{company_key}:{source_job_id}"


@dataclass
class Job:
    source: str
    source_job_id: str
    company: str
    company_key: str
    title: Optional[str] = None
    location: Optional[str] = None      # None = provider gave no location
    description: Optional[str] = None   # cleaned plain text
    posted_at: Optional[str] = None     # ISO-8601, as provided (never fabricated)
    updated_at: Optional[str] = None    # ISO-8601, as provided (never fabricated)
    apply_url: Optional[str] = None     # Greenhouse: exact absolute_url (job-status key in the UI)
    source_url: Optional[str] = None
    matched_keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise ValueError(f"Unknown source: {self.source!r}")
        for name in ("source_job_id", "company", "company_key"):
            value = getattr(self, name)
            if value is None or str(value).strip() == "":
                raise ValueError(f"Job.{name} is required")
        self.source_job_id = str(self.source_job_id)
        if not self.id:
            self.id = build_job_id(self.source, self.company_key, self.source_job_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "sourceJobId": self.source_job_id,
            "company": self.company,
            "companyKey": self.company_key,
            "title": self.title,
            "location": self.location,
            "description": self.description,
            "postedAt": self.posted_at,
            "updatedAt": self.updated_at,
            "applyUrl": self.apply_url,
            "sourceUrl": self.source_url,
            "matchedKeywords": list(self.matched_keywords),
            "metadata": dict(self.metadata),
        }
