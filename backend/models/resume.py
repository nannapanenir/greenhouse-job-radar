"""Tailoring session and related models (wire format = Resume Tailor's)."""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import Field

from .base import CamelModel
from .candidate import CandidateProfile
from .job import JobPosting

Mode = Literal["conservative", "balanced", "strong"]
ChangeStatus = Literal["pending", "accepted", "edited", "rejected"]
APPLIED_STATUSES = ("accepted", "edited")


class ProposedChange(CamelModel):
    id: str
    section: str = "Experience"
    company: str = ""
    bullet_label: str = ""
    target_bullet_id: str
    original: str
    updated: str
    keywords_added: list[str] = Field(default_factory=list)
    keywords_removed: list[str] = Field(default_factory=list)
    reason: str = ""
    evidence: str = ""
    status: ChangeStatus = "pending"
    edited_text: Optional[str] = None


class KeywordRow(CamelModel):
    keyword: str
    importance: Literal["Required", "Preferred"] = "Required"
    before: Union[int, float] = 0
    after: Union[int, float] = 0
    location: str = "Not added"
    status: Literal["Verified", "Unverified", "Not found"] = "Not found"


class MissingSkill(CamelModel):
    skill: str
    note: str = ""


class BlockedChange(CamelModel):
    """An AI suggestion the truth validator refused to show."""

    target_bullet_id: str = ""
    original: str = ""
    updated: str = ""
    reasons: list[str] = Field(default_factory=list)
    stage: int = 2  # 1 = reference rules (target/original/empty), 2 = evidence checks


class TailoringPreferences(CamelModel):
    focus_skills: list[str] = Field(default_factory=list)
    avoid_areas: list[str] = Field(default_factory=list)
    summary_style: Optional[Literal["shorter"]] = None


class TailoringSession(CamelModel):
    job_title: str = "Untitled Role"
    job: Optional[JobPosting] = None
    job_description_text: str = ""
    mode: Mode = "balanced"
    match_before: int = 0
    match_after: int = 0
    strong_matches: list[str] = Field(default_factory=list)
    still_missing: list[MissingSkill] = Field(default_factory=list)
    changes: list[ProposedChange] = Field(default_factory=list)
    keywords: list[KeywordRow] = Field(default_factory=list)
    blocked_changes: list[BlockedChange] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)   # validator fixes to AI claims
    warnings: list[str] = Field(default_factory=list)
    source: Literal["ai", "local"] = "local"
    provider: Optional[str] = None
    model: Optional[str] = None
    created_at: Optional[str] = None


class TailorRequest(CamelModel):
    candidate_profile: CandidateProfile
    job: Optional[JobPosting] = None
    job_description_text: Optional[str] = None
    mode: Mode = "balanced"
    preferences: TailoringPreferences = Field(default_factory=TailoringPreferences)


class GenerateRequest(CamelModel):
    candidate_profile: CandidateProfile
    session: Optional[TailoringSession] = None
    format: Literal["docx", "pdf"] = "docx"


class TailoredResume(CamelModel):
    """A generated resume version, linked to the job it was made for."""

    id: str
    job_id: str = ""
    company: str = ""
    title: str = ""
    created_at: str
    format: Literal["docx", "pdf"]
    mode: Mode = "balanced"
    applied_change_ids: list[str] = Field(default_factory=list)
    match_before: int = 0
    match_after: int = 0


class Application(CamelModel):
    """Future application tracking: which resume version went to which job."""

    job_id: str
    company: str = ""
    title: str = ""
    applied_at: Optional[str] = None
    status: str = "Applied"
    tailored_resume_id: Optional[str] = None
    resume_version: Optional[int] = None


__all__ = [
    "APPLIED_STATUSES", "Application", "BlockedChange", "CandidateProfile", "ChangeStatus",
    "GenerateRequest", "KeywordRow", "MissingSkill", "Mode", "ProposedChange", "TailorRequest",
    "TailoredResume", "TailoringPreferences", "TailoringSession",
]
