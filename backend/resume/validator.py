"""Truthfulness validator: the AI proposes, Python decides.

Stage 1 (port of tailorEngine.validateAndSanitize): a change must target a
real bullet id (or "summary"), its ``original`` must equal that text
exactly (trimmed), and ``updated`` must be non-empty. Protected fields
(employer, title, dates, education, certifications) are never targets, so
they can't be edited through a change at all.

Stage 2 (new): every change must be traceable to evidence in the verified
profile. A change is blocked, with reasons, if its new text
  * adds a technology/skill (lexicon, JD keywords or keywordsAdded) that is
    not evidenced — for an experience bullet the evidence must come from
    that same role (its technologies, bullets, projects); for the summary,
    anywhere in the profile;
  * introduces a number/metric not in the original or its evidence scope
    (fabricated metrics, inflated years of experience);
  * introduces seniority/title words the candidate never held;
  * introduces degrees/certifications not in the profile;
  * names a different employer from the profile.
Session-level claims are corrected too: a JD skill without evidence can't
be a "strong match" or a "Verified" keyword — it stays missing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .skills import contains_term, tech_lexicon

SENIORITY_TERMS = [
    "Senior", "Sr.", "Staff", "Principal", "Distinguished", "Manager", "Director", "Head of", "Architect",
    "VP", "Vice President", "Chief", "CTO", "CIO", "Team Lead", "Tech Lead", "Technical Lead",
    "Lead Engineer", "Lead Developer",
]
CREDENTIAL_TERMS = [
    "certified", "certification", "certificate", "degree", "bachelor", "bachelor's", "bachelors", "master's",
    "masters", "phd", "ph.d", "mba", "doctorate", "b.s.", "m.s.", "licensed",
]
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


@dataclass
class ValidationResult:
    accepted: list[dict] = field(default_factory=list)
    blocked: list[dict] = field(default_factory=list)   # {targetBulletId, original, updated, reasons, stage}
    # Position of each accepted change among stage-1 survivors (the Node
    # reference numbers auto-generated ids by that position).
    stage1_positions: list[int] = field(default_factory=list)
    stage2_blocked: int = 0


def bullet_index(profile: dict) -> dict[str, str]:
    """Port of collectBulletIndex: id -> verbatim text (summary included)."""
    index: dict[str, str] = {}
    if profile.get("summary") is not None:
        index["summary"] = (profile.get("summary") or {}).get("text", "")
    for exp in profile.get("experience") or []:
        for bullet in exp.get("bullets") or []:
            index[bullet.get("id")] = bullet.get("text", "")
    return index


def _experience_for(profile: dict, bullet_id: str) -> Optional[dict]:
    for exp in profile.get("experience") or []:
        if any(b.get("id") == bullet_id for b in exp.get("bullets") or []):
            return exp
    return None


def _experience_evidence(exp: dict) -> str:
    parts = [*exp.get("technologies", []), *(b.get("text", "") for b in exp.get("bullets") or [])]
    for project in exp.get("projects") or []:
        parts += [project.get("name", ""), project.get("description", ""), *project.get("technologies", [])]
    return "\n".join(parts)


def profile_evidence(profile: dict) -> str:
    """All verified facts as text (skills, roles, bullets, education, certs)."""
    parts = [(profile.get("summary") or {}).get("text", "")]
    parts += [s.get("name", "") for s in profile.get("skills") or []]
    for exp in profile.get("experience") or []:
        parts += [exp.get("company", ""), exp.get("title", ""), exp.get("startDate", ""), exp.get("endDate", ""),
                  exp.get("location", ""), _experience_evidence(exp)]
    for edu in profile.get("education") or []:
        parts += [edu.get("degree", ""), edu.get("institution", ""), edu.get("endDate", "")]
    for cert in profile.get("certifications") or []:
        parts += [cert.get("name", ""), cert.get("issuer", ""), cert.get("year", "")]
    return "\n".join(p for p in parts if p)


def is_evidenced(term: str, evidence: str) -> bool:
    return contains_term(evidence, term)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text or "")}


def _introduced(terms: Iterable[str], original: str, updated: str) -> list[str]:
    return [t for t in terms if contains_term(updated, t) and not contains_term(original, t)]


def check_change(change: dict, profile: dict, *, jd_keywords: Iterable[str] = ()) -> list[str]:
    """Stage-2 reasons this change is not supported (empty list = OK)."""
    target = change.get("targetBulletId")
    original = change.get("original", "")
    updated = change.get("updated", "")
    reasons: list[str] = []

    all_evidence = profile_evidence(profile)
    if target == "summary":
        scope_label, scope = "your profile", all_evidence
    else:
        exp = _experience_for(profile, target) or {}
        scope_label = exp.get("company") or "this role"
        scope = "\n".join([original, _experience_evidence(exp)])

    # 1. Skills / technologies
    claimed = list(dict.fromkeys([*(change.get("keywordsAdded") or []), *_introduced(tech_lexicon(jd_keywords), original, updated)]))
    for term in claimed:
        if isinstance(term, str) and term.strip() and not is_evidenced(term, scope):
            reasons.append(f'Unsupported skill "{term}": no evidence in {scope_label}.')

    # 2. Numbers / metrics / years
    new_numbers = _numbers(updated) - _numbers(original) - _numbers(scope)
    for number in sorted(new_numbers):
        reasons.append(f'Unsupported number/metric "{number}": not in the original line or its evidence.')

    # 3. Titles / seniority
    titles = "\n".join(e.get("title", "") for e in profile.get("experience") or [])
    for term in _introduced(SENIORITY_TERMS, original, updated):
        if not contains_term(titles, term):
            reasons.append(f'Title/seniority "{term}" was never one of your job titles.')

    # 4. Degrees / certifications
    credentials = "\n".join(
        [f"{e.get('degree', '')} {e.get('institution', '')}" for e in profile.get("education") or []]
        + [f"{c.get('name', '')} {c.get('issuer', '')}" for c in profile.get("certifications") or []]
    )
    for term in _introduced(CREDENTIAL_TERMS, original, updated):
        if not contains_term(credentials, term):
            reasons.append(f'Credential claim "{term}" is not in your education/certifications.')

    # 5. Employers: a bullet may not name a different employer.
    own_company = "" if target == "summary" else (_experience_for(profile, target) or {}).get("company", "")
    for exp in profile.get("experience") or []:
        company = exp.get("company", "")
        if company and company != own_company and _introduced([company], original, updated):
            reasons.append(f'Mentions a different employer ("{company}").')

    return reasons


def validate_changes(raw_changes: list, profile: dict, *, jd_keywords: Iterable[str] = (),
                     evidence_checks: bool = True) -> ValidationResult:
    """Stage 1 (exact reference rules) + stage 2 (evidence). Order preserved.

    ``evidence_checks=False`` runs stage 1 only (= Node reference behaviour),
    used by the parity harness.
    """
    index = bullet_index(profile)
    result = ValidationResult()
    jd_keywords = list(jd_keywords)
    stage1_survivors = 0

    for change in raw_changes if isinstance(raw_changes, list) else []:
        if not isinstance(change, dict):
            continue
        target = change.get("targetBulletId")
        updated = change.get("updated")
        base = {"targetBulletId": str(target or ""), "original": str(change.get("original") or ""),
                "updated": str(updated or "")}

        stage1 = []
        if not target or target not in index:
            stage1.append("Targets a line that isn't in your profile (only bullets and the summary can change).")
        elif not isinstance(change.get("original"), str) or change["original"].strip() != index[target].strip():
            stage1.append("Its 'original' text doesn't exactly match your profile.")
        if not isinstance(updated, str) or not updated.strip():
            stage1.append("The proposed text is empty.")
        if stage1:
            result.blocked.append({**base, "reasons": stage1, "stage": 1})
            continue

        position = stage1_survivors
        stage1_survivors += 1
        reasons = check_change(change, profile, jd_keywords=jd_keywords) if evidence_checks else []
        if reasons:
            result.blocked.append({**base, "reasons": reasons, "stage": 2})
            result.stage2_blocked += 1
        else:
            result.accepted.append(change)
            result.stage1_positions.append(position)
    return result


def correct_session_claims(session: dict, profile: dict) -> list[str]:
    """Missing skills stay missing: fix keyword statuses/strong matches the
    AI claimed without evidence. Mutates ``session``; returns notes."""
    evidence = profile_evidence(profile)
    notes: list[str] = []

    for row in session.get("keywords") or []:
        if row.get("status") == "Verified" and not is_evidenced(row["keyword"], evidence):
            row.update(status="Not found", before=0, after=0, location="Not added")
            notes.append(f'"{row["keyword"]}" was marked Verified but isn\'t in your profile — marked Not found.')

    missing = {m["skill"].lower() for m in session.get("stillMissing") or []}
    strong = []
    for skill in session.get("strongMatches") or []:
        if is_evidenced(skill, evidence):
            strong.append(skill)
            continue
        notes.append(f'"{skill}" was listed as a strong match without evidence — moved to Still missing.')
        if skill.lower() not in missing:
            session.setdefault("stillMissing", []).append({"skill": skill, "note": "Not present in your verified profile."})
            missing.add(skill.lower())
    session["strongMatches"] = strong

    for row in session.get("keywords") or []:
        if row.get("status") == "Not found" and row["keyword"].lower() not in missing:
            session.setdefault("stillMissing", []).append({"skill": row["keyword"], "note": "Not present in your verified profile."})
            missing.add(row["keyword"].lower())
    return notes
