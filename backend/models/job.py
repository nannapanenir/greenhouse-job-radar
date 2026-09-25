"""The Phase 1 Common Job contract, as Resume AI consumes it.

Resume AI is provider-independent: it only reads these fields, whether the
job came from Greenhouse, Lever, Ashby or was pasted manually.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from .base import CamelModel


class JobPosting(CamelModel):
    id: str = ""
    source: str = "manual"          # greenhouse | lever | ashby | manual
    source_job_id: str = ""
    company: str = ""
    company_key: str = ""
    title: str = ""
    location: Optional[str] = None
    description: str = ""
    posted_at: Optional[str] = None
    updated_at: Optional[str] = None
    apply_url: Optional[str] = None
    source_url: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
