"""Candidate profile (the verified "Career Profile").

Shape matches the standalone Resume Tailor JSON so profiles move between
the two apps unchanged. Fields marked ``protected`` are facts tailoring may
never change (employer, title, dates, degree, institution, certification).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from .base import CamelModel

PROTECTED = {"protected": True}

# section -> protected field names (camelCase, as in JSON)
PROTECTED_FIELDS: dict[str, tuple[str, ...]] = {
    "experience": ("company", "title", "startDate", "endDate"),
    "education": ("degree", "institution", "endDate"),
    "certifications": ("name", "issuer", "year"),
}

# Verification status used across the profile.
STATUSES = ("extracted", "user-confirmed", "user-added", "unverified")


class PersonalInformation(CamelModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linked_in: str = ""
    portfolio: str = ""


class Summary(CamelModel):
    text: str = ""
    status: str = "extracted"


class Skill(CamelModel):
    name: str
    status: str = "extracted"


class Bullet(CamelModel):
    id: str
    text: str
    status: str = "extracted"


class Project(CamelModel):
    name: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    status: str = "user-added"


class Experience(CamelModel):
    id: str
    company: str = Field(json_schema_extra=PROTECTED)
    title: str = Field(default="", json_schema_extra=PROTECTED)
    start_date: str = Field(default="", json_schema_extra=PROTECTED)
    end_date: str = Field(default="", json_schema_extra=PROTECTED)
    location: str = ""
    status: str = "extracted"
    technologies: list[str] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)


class Education(CamelModel):
    id: str
    degree: str = Field(default="", json_schema_extra=PROTECTED)
    institution: str = Field(default="", json_schema_extra=PROTECTED)
    end_date: str = Field(default="", json_schema_extra=PROTECTED)
    status: str = "extracted"


class Certification(CamelModel):
    id: str
    name: str = Field(json_schema_extra=PROTECTED)
    issuer: str = Field(default="", json_schema_extra=PROTECTED)
    year: str = Field(default="", json_schema_extra=PROTECTED)
    status: str = "extracted"


class CandidateProfile(CamelModel):
    personal_information: PersonalInformation = Field(default_factory=PersonalInformation)
    summary: Summary = Field(default_factory=Summary)
    skills: list[Skill] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    awards: list[Any] = Field(default_factory=list)


class MasterResume(CamelModel):
    """Metadata about the uploaded source resume (the file itself is not stored)."""

    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    sha256: str
    file_type: str            # "pdf" | "docx"
    page_count: Optional[int] = None
    text_length: int
    uploaded_at: str


def protected_facts(profile: dict) -> list[tuple[str, str, str, str]]:
    """Every protected fact as (section, id, field, value), for tamper checks."""
    facts = []
    for section, fields in PROTECTED_FIELDS.items():
        for entry in profile.get(section) or []:
            if not isinstance(entry, dict):
                continue
            for field in fields:
                facts.append((section, str(entry.get("id", "")), field, str(entry.get(field, ""))))
    return facts
