"""(CandidateProfile + job + mode) -> TailoringSession.

Port of resume-tailor/server/tailorEngine.js: same system prompt, mode
instructions and sanitization. Every change then goes through
``validator.validate_changes`` and session claims through
``validator.correct_session_claims``.

Fallback (same as the standalone app's chat.js): no AI configured, or the
AI call fails -> local engine, with a warning explaining why.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from ..ai import AIError, AIProvider, complete_with_retry, extract_json_object
from . import fallback_engine, validator
from .text import clamp_pct, finite_number, js_round

log = logging.getLogger("backend.resume")

SYSTEM_PROMPT = """You are a resume-tailoring engine. You are given a candidate's VERIFIED career profile as JSON and a job description. Produce truthful, evidence-based resume tailoring suggestions.

STRICT RULES (never violate):
- Never invent skills, projects, certifications, achievements, or measurements that are not present in the profile JSON.
- Never propose changing company names, job titles, employment dates, or education/degrees.
- Every "original" field in a change must be copied verbatim (exact text) from the profile: either a bullet's "text" or the summary's "text", identified by targetBulletId ("summary" for the summary).
- Every "evidence" field must cite the specific fact in the profile that justifies the change.
- Do not keyword-stuff. Only add a keyword to a bullet if the underlying work already verifiably involved it per the profile's technologies/skills lists.
- matchBefore and matchAfter are integers 0-100 describing an "Estimated Resume Relevance", not a real ATS score. Be conservative and explainable.
- If there is no truthful way to strengthen a bullet for this job description, return an empty changes array rather than fabricating one.

Respond with ONLY a single JSON object, no markdown code fences, no prose before or after, matching exactly this shape:
{
  "jobTitle": string,
  "matchBefore": number,
  "matchAfter": number,
  "strongMatches": string[],
  "stillMissing": [{"skill": string, "note": string}],
  "changes": [{
    "id": string, "section": string, "company": string, "bulletLabel": string,
    "targetBulletId": string, "original": string, "updated": string,
    "keywordsAdded": string[], "keywordsRemoved": string[], "reason": string, "evidence": string
  }],
  "keywords": [{"keyword": string, "importance": "Required" or "Preferred", "before": number, "after": number, "location": string, "status": "Verified" or "Unverified" or "Not found"}]
}"""

MODE_INSTRUCTIONS = {
    "conservative": "Conservative mode: propose the fewest possible changes, touching only bullets that map to explicitly REQUIRED job skills already verified in the profile.",
    "balanced": "Balanced mode: strengthen bullets for both required and preferred skills that are verified in the profile.",
    "strong": "Strong Targeting mode: also strengthen the professional summary using verified specialties, in addition to required and preferred skills.",
}


class TailoringError(ValueError):
    pass


def _preference_text(preferences: dict) -> str:
    lines = []
    if preferences.get("focusSkills"):
        lines.append(f"Emphasize these skills where the profile verifiably supports them: {', '.join(preferences['focusSkills'])}.")
    if preferences.get("avoidAreas"):
        lines.append(f"Do not make the candidate look {', '.join(preferences['avoidAreas'])}-heavy; don't add {', '.join(preferences['avoidAreas'])} keywords.")
    if preferences.get("summaryStyle") == "shorter":
        lines.append('Propose a shorter summary (targetBulletId "summary") using only facts already in the summary.')
    return ("\n\nUSER PREFERENCES (still subject to every rule above):\n" + "\n".join(lines)) if lines else ""


def build_user_prompt(profile: dict, job_description_text: str, mode: str, preferences: Optional[dict] = None) -> str:
    return (
        f"CAREER PROFILE (verified facts only):\n{json.dumps(profile, separators=(',', ':'), ensure_ascii=False)}\n\n"
        f"JOB DESCRIPTION:\n{job_description_text}\n\n"
        f"TAILORING MODE: {mode}. {MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS['balanced'])}"
        f"{_preference_text(preferences or {})}\n\n"
        "Respond with only the JSON object described in the system prompt."
    )


def _strings(value) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def sanitize_ai_session(raw: str, profile: dict) -> dict:
    """Port of validateAndSanitize (field shapes, defaults, clamping). Changes
    are kept raw here; ``finalize_session`` runs the validator on them."""
    try:
        parsed = extract_json_object(raw)
    except ValueError as error:
        log.error("[tailor] Failed to parse AI response: %s", error)
        raise TailoringError("The AI response was not valid JSON. Check the server log for details.") from None
    if not isinstance(parsed, dict):
        raise TailoringError("The AI response was not a JSON object.")

    keywords = []
    for k in parsed.get("keywords") if isinstance(parsed.get("keywords"), list) else []:
        if not (isinstance(k, dict) and isinstance(k.get("keyword"), str)):
            continue
        keywords.append({
            "keyword": k["keyword"],
            "importance": "Preferred" if k.get("importance") == "Preferred" else "Required",
            "before": finite_number(k.get("before")),
            "after": finite_number(k.get("after")),
            "location": k["location"] if isinstance(k.get("location"), str) else "Not added",
            "status": k["status"] if k.get("status") in ("Verified", "Unverified", "Not found") else "Not found",
        })

    still_missing = [
        {"skill": g["skill"], "note": g["note"] if isinstance(g.get("note"), str) else ""}
        for g in (parsed.get("stillMissing") if isinstance(parsed.get("stillMissing"), list) else [])
        if isinstance(g, dict) and isinstance(g.get("skill"), str)
    ]

    return {
        "jobTitle": parsed["jobTitle"] if isinstance(parsed.get("jobTitle"), str) and parsed["jobTitle"] else "Untitled Role",
        "matchBefore": clamp_pct(parsed.get("matchBefore")),
        "matchAfter": clamp_pct(parsed.get("matchAfter")),
        "strongMatches": _strings(parsed.get("strongMatches")),
        "stillMissing": still_missing,
        "changes": parsed.get("changes") if isinstance(parsed.get("changes"), list) else [],
        "keywords": keywords,
        "source": "ai",
    }


def normalize_change(change: dict, index: int) -> dict:
    """Port of the validateAndSanitize change mapper."""
    target = change["targetBulletId"]
    return {
        "id": change["id"] if isinstance(change.get("id"), str) and change["id"] else f"ai-{index}-{target}",
        "section": change["section"] if isinstance(change.get("section"), str) else "Experience",
        "company": change["company"] if isinstance(change.get("company"), str) else "",
        "bulletLabel": change["bulletLabel"] if isinstance(change.get("bulletLabel"), str) else "",
        "targetBulletId": target,
        "original": change["original"],
        "updated": change["updated"],
        "keywordsAdded": _strings(change.get("keywordsAdded")),
        "keywordsRemoved": _strings(change.get("keywordsRemoved")),
        "reason": change["reason"] if isinstance(change.get("reason"), str) else "",
        "evidence": change["evidence"] if isinstance(change.get("evidence"), str) else "",
        "status": "pending",
    }


def finalize_session(session: dict, profile: dict, *, mode: str = "balanced", evidence_checks: bool = True) -> dict:
    """Run the truth validator over changes + claims (AI and local alike)."""
    jd_keywords = [k["keyword"] for k in session.get("keywords") or []]
    proposed = len(session.get("changes") or [])
    result = validator.validate_changes(
        session.get("changes") or [], profile, jd_keywords=jd_keywords, evidence_checks=evidence_checks
    )
    session["changes"] = [normalize_change(c, i) for c, i in zip(result.accepted, result.stage1_positions)]
    session["blockedChanges"] = result.blocked
    corrections = validator.correct_session_claims(session, profile) if evidence_checks else []

    # The proposed "after" score must not count changes that were blocked.
    if result.stage2_blocked:
        kept = len(session["changes"])
        before, after = session["matchBefore"], session["matchAfter"]
        if session.get("source") == "local":
            bonus = 5 if mode == "strong" else 0 if mode == "conservative" else 3
            new_after = max(5, min(97, before + kept * 4 + (bonus if kept else 0)))
        else:
            survivors = kept + result.stage2_blocked
            new_after = js_round(before + (after - before) * (kept / survivors)) if survivors else before
        if new_after != after:
            session["matchAfter"] = new_after
            corrections.append(
                f"Estimated relevance after tailoring lowered from {after}% to {new_after}% because "
                f"{result.stage2_blocked} suggested change(s) were blocked."
            )
    session["corrections"] = corrections
    return session


def job_description_for(job: Optional[dict], text: Optional[str]) -> str:
    if text and text.strip():
        return text
    if job:
        header = "\n".join(p for p in [job.get("title"), job.get("company"), job.get("location")] if p)
        return f"{header}\n\n{job.get('description') or ''}".strip()
    return ""


async def tailor(
    profile: dict,
    job_description_text: str,
    mode: str = "balanced",
    *,
    provider: Optional[AIProvider] = None,
    job: Optional[dict] = None,
    preferences: Optional[dict] = None,
) -> dict:
    if not job_description_text.strip():
        raise TailoringError("A job description is required.")
    warnings: list[str] = []
    session: Optional[dict] = None

    if provider is not None:
        try:
            content = await complete_with_retry(
                provider,
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(profile, job_description_text, mode, preferences)},
                ],
            )
            session = sanitize_ai_session(content, profile)
            session.update(provider=provider.name, model=provider.model)
        except (AIError, TailoringError) as error:
            warnings.append(f"{provider.label} tailoring failed ({error}). Used the built-in local matching engine instead.")
    else:
        warnings.append("No AI provider configured — used the built-in local matching engine.")

    if session is None:
        session = fallback_engine.build_session_from_jd(job_description_text, profile, mode, preferences)

    session = finalize_session(session, profile, mode=mode)
    if job and job.get("title"):
        session["jobTitle"] = job["title"]
    session.update(
        job=job,
        jobDescriptionText=job_description_text,
        mode=mode,
        warnings=warnings,
        createdAt=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    return session
