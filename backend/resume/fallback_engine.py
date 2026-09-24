"""Local, explainable tailoring engine (no AI).

Port of buildSessionFromJD / analyzeJobDescription / computeAdjustedAfterScore
from resume-tailor/public/js/mockData.js. Used when no AI provider is
configured or the AI call fails. It only reuses text and skills already in
the profile.

Intentional differences (documented, covered by tests):
  * profile skills/technologies match JD skills case-insensitively
    ("Typescript" in a profile now counts for "TypeScript");
  * no "Strong" summary change is proposed when the summary is empty;
  * optional preferences (focus/avoid/shorter summary) from Resume AI chat.
With default preferences and canonical casing the output is identical to
the Node reference (scripts/resume-parity.mjs).
"""

from __future__ import annotations

import re
from typing import Optional

from .skills import KNOWN_SKILLS, extract_skills_from_text
from .text import js_round

BACKEND_SKILLS = {"java", "spring boot", "node.js", "sql", "postgresql", "mongodb", "microservices", "rest apis", "python"}
MISSING_NOTE = "Not present in any verified profile entry. Add it under Career Profile to include it in future tailoring."

# JS `.` excludes \n, \r,  ,   (no `s` flag).
_TITLE_RE = re.compile(
    r"^([^\n\r  ]{0,60}?(engineer|developer|architect|lead|manager)[^\n]{0,20})", re.IGNORECASE
)


def analyze_job_description(text: str) -> dict:
    marker = re.search(r"preferred|nice to have|bonus", text, re.IGNORECASE)
    required_text, preferred_text = (text[: marker.start()], text[marker.start():]) if marker else (text, "")
    required = extract_skills_from_text(required_text)
    preferred_only = [s for s in extract_skills_from_text(preferred_text) if s not in required]
    title = _TITLE_RE.match(text)
    return {
        "jobTitle": title.group(1).strip() if title else "Untitled Role",
        "requiredSkills": required,
        "preferredSkills": preferred_only,
    }


def profile_skill_names(profile: dict) -> set[str]:
    names = {s.get("name", "") for s in profile.get("skills") or []}
    for exp in profile.get("experience") or []:
        names.update(exp.get("technologies") or [])
    return {n.lower() for n in names if n}


def _find_bullets_for_skill(profile: dict, skill: str) -> list[tuple[dict, dict]]:
    skill_lower = skill.lower()
    hits = []
    for exp in profile.get("experience") or []:
        techs = {t.lower() for t in exp.get("technologies") or []}
        for bullet in exp.get("bullets") or []:
            if skill_lower in techs or skill_lower in bullet.get("text", "").lower():
                hits.append((exp, bullet))
    return hits


def _strip_period(text: str) -> str:
    return text[:-1] if text.endswith(".") else text


def _first_sentence(text: str) -> str:
    match = re.match(r"(.+?[.!?])(\s|$)", text.strip())
    return match.group(1) if match else text.strip()


def build_session_from_jd(job_text: str, profile: dict, mode: str = "balanced",
                          preferences: Optional[dict] = None) -> dict:
    preferences = preferences or {}
    parsed = analyze_job_description(job_text)
    verified = profile_skill_names(profile)
    has = lambda s: s.lower() in verified  # noqa: E731

    required_matched = [s for s in parsed["requiredSkills"] if has(s)]
    required_missing = [s for s in parsed["requiredSkills"] if not has(s)]
    preferred_matched = [s for s in parsed["preferredSkills"] if has(s)]
    preferred_missing = [s for s in parsed["preferredSkills"] if not has(s)]

    total_required = len(parsed["requiredSkills"]) or 1
    total_preferred = len(parsed["preferredSkills"])
    match_before = js_round(
        (len(required_matched) / total_required) * 70
        + ((len(preferred_matched) / total_preferred) * 20 if total_preferred else 10)
    )

    skills_for_changes = required_matched if mode == "conservative" else required_matched + preferred_matched

    # Preferences (Resume AI chat): focus first, drop avoided areas. Never adds unverified skills.
    focus = [f.lower() for f in preferences.get("focusSkills") or []]
    if focus:
        skills_for_changes = sorted(skills_for_changes, key=lambda s: 0 if s.lower() in focus else 1)
    if "backend" in [a.lower() for a in preferences.get("avoidAreas") or []]:
        skills_for_changes = [s for s in skills_for_changes if s.lower() not in BACKEND_SKILLS]

    changes: list[dict] = []
    used: set[str] = set()
    for idx, skill in enumerate(skills_for_changes):
        hits = _find_bullets_for_skill(profile, skill)
        if not hits:
            continue
        exp, bullet = hits[0]
        if bullet["id"] in used:
            continue
        used.add(bullet["id"])
        changes.append({
            "id": f"gen-{idx}-{bullet['id']}",
            "section": "Experience",
            "company": exp.get("company", ""),
            "bulletLabel": f"Bullet {exp['bullets'].index(bullet) + 1}",
            "targetBulletId": bullet["id"],
            "original": bullet["text"],
            "updated": f"{_strip_period(bullet['text'])}, leveraging {skill} to directly address this role's requirements.",
            "keywordsAdded": [skill],
            "keywordsRemoved": [],
            "reason": f"The job description requires {skill}, and this bullet already demonstrates it but did not name it explicitly.",
            "evidence": f"Verified in Career Profile: {exp.get('company', '')} technologies include {skill}.",
            "status": "pending",
        })

    summary_text = (profile.get("summary") or {}).get("text", "")
    if preferences.get("summaryStyle") == "shorter" and summary_text:
        shorter = _first_sentence(summary_text)
        if shorter and shorter != summary_text.strip():
            changes.append({
                "id": "gen-summary-short", "section": "Summary", "company": "", "bulletLabel": "",
                "targetBulletId": "summary", "original": summary_text, "updated": shorter,
                "keywordsAdded": [], "keywordsRemoved": [],
                "reason": "You asked for a shorter summary; this keeps its first sentence verbatim.",
                "evidence": "Taken word-for-word from your verified summary.", "status": "pending",
            })
    elif mode == "strong" and skills_for_changes and summary_text:
        top = skills_for_changes[:3]
        changes.append({
            "id": "gen-summary", "section": "Summary", "company": "", "bulletLabel": "",
            "targetBulletId": "summary", "original": summary_text,
            "updated": f"{_strip_period(summary_text)}, specializing in {', '.join(top)} for {parsed['jobTitle']} roles.",
            "keywordsAdded": top, "keywordsRemoved": [],
            "reason": "Strong Targeting mode strengthens the summary with verified specialties that match the job title and top requirements.",
            "evidence": f"Verified in Career Profile: skills list includes {', '.join(top)}.",
            "status": "pending",
        })

    mode_bonus = 5 if mode == "strong" else 0 if mode == "conservative" else 3
    match_after = min(97, match_before + len(changes) * 4 + (mode_bonus if changes else 0))

    def rows(skills, importance, before, after, location, status):
        return [{"keyword": s, "importance": importance, "before": before, "after": after, "location": location, "status": status}
                for s in skills]

    keywords = (
        rows(required_matched, "Required", 1, 2, "Skills, Experience", "Verified")
        + rows(required_missing, "Required", 0, 0, "Not added", "Not found")
        + rows(preferred_matched, "Preferred", 1, 1, "Skills, Experience", "Verified")
        + rows(preferred_missing, "Preferred", 0, 0, "Not added", "Not found")
    )

    return {
        "jobTitle": parsed["jobTitle"],
        "jobDescriptionText": job_text,
        "matchBefore": max(5, min(95, match_before)),
        "matchAfter": max(5, min(97, match_after)),
        "strongMatches": [*required_matched, *preferred_matched],
        "stillMissing": [{"skill": s, "note": MISSING_NOTE} for s in [*required_missing, *preferred_missing]],
        "changes": changes,
        "keywords": keywords,
        "source": "local",
    }


def compute_adjusted_after_score(session: dict) -> int:
    """Port of computeAdjustedAfterScore: scale by accepted/edited share."""
    changes = session.get("changes") or []
    if not changes:
        return session.get("matchBefore", 0)
    applied = sum(1 for c in changes if c.get("status") in ("accepted", "edited")) / len(changes)
    return js_round(session["matchBefore"] + (session["matchAfter"] - session["matchBefore"]) * applied)


__all__ = ["KNOWN_SKILLS", "analyze_job_description", "build_session_from_jd", "compute_adjusted_after_score"]
