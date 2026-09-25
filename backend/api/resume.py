"""Resume AI endpoints."""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import Field

from .. import config
from ..ai import AIError, create_provider
from ..models.base import CamelModel
from ..models.candidate import CandidateProfile
from ..models.job import JobPosting
from ..models.resume import GenerateRequest, ProposedChange, TailoringSession, TailorRequest
from ..resume import chat, fallback_engine, tailor, validator
from ..resume.apply import ProtectedFactError, build_tailored_profile
from ..resume.docx_generator import build_resume_docx
from ..resume.parser import DOCUMENT_TYPES, MAX_FILE_BYTES, MAX_FILE_LABEL, ResumeParseError, parse_document, parse_resume
from ..resume.pdf_generator import build_resume_pdf
from ..resume.profile_extractor import ProfileExtractionError, extract_profile

router = APIRouter(prefix="/api/resume", tags=["resume"])

MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"File is too large (max {MAX_FILE_LABEL}).")
    return data


def _parse_error(error: ResumeParseError) -> HTTPException:
    return HTTPException(status_code=400, detail={"message": str(error), "code": error.code})


def _provider():
    return create_provider(config.load_ai_settings())


@router.post("/parse")
async def parse(file: UploadFile = File(...)) -> dict:
    """Master resume (PDF/DOCX) -> text -> AI -> Candidate Profile."""
    data = await _read_upload(file)
    try:
        document = parse_resume(file.filename or "", data, file.content_type)
    except ResumeParseError as error:
        raise _parse_error(error) from None

    provider = _provider()
    if provider is None:
        raise HTTPException(status_code=400, detail="AI provider is not configured yet. Set one up in Settings.")
    try:
        profile = await extract_profile(provider, document.text)
    except (AIError, ProfileExtractionError) as error:
        raise HTTPException(status_code=502, detail=str(error) or "Resume parsing failed.") from None
    return {
        "profile": CandidateProfile.model_validate(profile).dump(),
        "masterResume": document.metadata(),
    }


@router.post("/extract-text")
async def extract_text(file: UploadFile = File(...)) -> dict:
    """Any supported document (PDF/DOCX/TXT) -> raw text. Used for job descriptions."""
    data = await _read_upload(file)
    try:
        document = parse_document(file.filename or "", data, file.content_type, allowed=DOCUMENT_TYPES)
    except ResumeParseError as error:
        raise _parse_error(error) from None
    return {"text": document.text, "metadata": document.metadata()}


class AnalyzeRequest(CamelModel):
    candidate_profile: CandidateProfile
    job: Optional[JobPosting] = None
    job_description_text: Optional[str] = None


@router.post("/analyze")
def analyze(body: AnalyzeRequest) -> dict:
    """Deterministic fit analysis (no AI, no changes): what matches, what's missing."""
    profile = body.candidate_profile.dump()
    job = body.job.dump() if body.job else None
    text = tailor.job_description_for(job, body.job_description_text)
    if not text.strip():
        raise HTTPException(status_code=400, detail="A job description is required.")
    session = fallback_engine.build_session_from_jd(text, profile, "balanced")
    notes = validator.correct_session_claims(session, profile)
    return {
        "jobTitle": (job or {}).get("title") or session["jobTitle"],
        "matchBefore": session["matchBefore"],
        "strongMatches": session["strongMatches"],
        "stillMissing": session["stillMissing"],
        "keywords": session["keywords"],
        "corrections": notes,
    }


@router.post("/tailor", response_model=TailoringSession)
async def tailor_resume(body: TailorRequest) -> dict:
    profile = body.candidate_profile.dump()
    job = body.job.dump() if body.job else None
    text = tailor.job_description_for(job, body.job_description_text)
    if not text.strip():
        raise HTTPException(status_code=400, detail="careerProfile and a job description are required.")
    try:
        return await tailor.tailor(
            profile, text, body.mode, provider=_provider(), job=job, preferences=body.preferences.dump(),
        )
    except tailor.TailoringError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None


class CheckChangeRequest(CamelModel):
    candidate_profile: CandidateProfile
    change: ProposedChange
    jd_keywords: list[str] = Field(default_factory=list)
    job_title: str = ""


@router.post("/check-change")
def check_change(body: CheckChangeRequest) -> dict:
    """Validate a user edit or regenerated phrasing before it's accepted."""
    change = body.change.dump()
    if change.get("editedText") is not None:
        change["updated"] = change["editedText"]
    result = validator.validate_changes([change], body.candidate_profile.dump(), jd_keywords=body.jd_keywords,
                                        job_title=body.job_title)
    reasons = result.blocked[0]["reasons"] if result.blocked else []
    return {"ok": not reasons, "reasons": reasons}


class TailoredProfileRequest(CamelModel):
    candidate_profile: CandidateProfile
    session: Optional[TailoringSession] = None


@router.post("/tailored-profile")
def tailored_profile(body: TailoredProfileRequest) -> dict:
    master = body.candidate_profile.dump()
    try:
        profile, applied, skipped, overrides = build_tailored_profile(master, body.session.dump() if body.session else None)
    except ProtectedFactError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    return {"profile": profile, "appliedChangeIds": applied, "skipped": skipped, "userOverrides": overrides}


def _file_base_name(profile: dict, session: Optional[dict]) -> str:
    """Port of jobMatchPanel.resumeFileBaseName."""
    def clean(text: str) -> str:
        return re.sub(r"\s+", "_", re.sub(r"[^\w\s-]", "", (text or "").strip(), flags=re.ASCII))
    name = clean((profile.get("personalInformation") or {}).get("fullName", "")) or "Candidate"
    title = clean((session or {}).get("jobTitle", "")) or "Resume"
    return f"{name}_{title}"


@router.post("/generate")
def generate(body: GenerateRequest) -> Response:
    """Master profile + reviewed session -> DOCX/PDF. Only accepted/edited changes are applied."""
    master = body.candidate_profile.dump()
    session = body.session.dump() if body.session else None
    try:
        profile, applied, skipped, overrides = build_tailored_profile(master, session)
    except ProtectedFactError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None

    content = build_resume_pdf(profile) if body.format == "pdf" else build_resume_docx(profile)
    filename = f"{_file_base_name(master, session)}_Resume.{body.format}"
    return Response(
        content=content,
        media_type=MIME[body.format],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Applied-Changes": ",".join(applied),
            "X-Skipped-Changes": str(len(skipped)),
            "X-User-Overrides": ",".join(overrides),
            "Access-Control-Expose-Headers": "Content-Disposition, X-Applied-Changes, X-Skipped-Changes, X-User-Overrides",
        },
    )


class ChatRequest(CamelModel):
    message: str
    candidate_profile: Optional[CandidateProfile] = None
    session: Optional[TailoringSession] = None
    job: Optional[JobPosting] = None
    job_description_text: Optional[str] = None
    active_change_id: Optional[str] = None


class ChatResponse(CamelModel):
    operation: Literal[chat.OPERATIONS]  # type: ignore[valid-type]
    reply: str
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/chat", response_model=ChatResponse)
def chat_message(body: ChatRequest) -> dict:
    return chat.route_message(
        body.message,
        profile=body.candidate_profile.dump() if body.candidate_profile else None,
        session=body.session.dump() if body.session else None,
        has_job=bool(body.job or (body.job_description_text or "").strip()),
        active_change_id=body.active_change_id,
    )
