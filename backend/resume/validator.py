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
  * names a different employer from the profile;
  * introduces a new named entity — a technology, organization, product or
    place that reads as a proper noun (capitalized mid-sentence, CamelCase,
    C#/Node.js/.NET-style, letter+digit tokens) — that appears neither in
    the original line nor in its evidence scope. This is the general rule
    that catches "Rust", "Go" or "at Google" without any static list;
  * introduces a word-form metric ("doubling", "tenfold", "hundreds of");
  * introduces leadership/scope claims ("led", "managed a team",
    "mentored", "team of") the role's evidence or title doesn't support.
Ordinary rewording of existing evidence (lower-case words, reordering)
passes. Session-level claims are corrected too: a JD skill without evidence can't
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

# Capitalized acronyms that are generic vocabulary, not factual claims.
GENERIC_CAPS = {
    "api", "apis", "ui", "ux", "qa", "url", "urls", "http", "https", "json", "xml", "csv", "pdf", "saas", "sdk",
    "ide", "os", "it", "id", "mvp", "kpi", "kpis", "sla", "slas", "roi", "b2b", "b2c", "crud", "i", "ok", "etc",
}
_TOKEN = re.compile(r"[A-Za-z0-9.#+][A-Za-z0-9+#./'\u2019-]*")
_SENTENCE_BREAK = re.compile(r"(^|[.!?:;\u2022\n(\[\u2013\u2014]|\s-)\s*$")

WORD_METRIC = re.compile(
    r"\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|hundreds?|"
    r"thousands?|millions?|billions?|dozens?|doubled?|doubles|doubling|tripled?|triples|tripling|quadrupl(?:e|ed|es|ing)|"
    r"halv(?:ed|es|ing)|twice|twofold|threefold|fourfold|fivefold|tenfold|percent)\b",
    re.IGNORECASE,
)
_PEOPLE = r"(?:team|teams|engineers|developers|people|staff|reports|interns|contractors|analysts|designers)"
LEADERSHIP = [
    ("led", r"\bled\b"),
    ("leading", rf"\bleading\s+(?:a|an|the|teams?|engineers|developers|efforts?|initiatives?|{_PEOPLE})\b"),
    ("spearheaded", r"\bspearhead(?:ed|ing|s)?\b"),
    ("oversaw", r"\boversaw\b|\boversee(?:s|ing)?\b"),
    ("supervised", r"\bsupervis(?:ed|es|ing|or)\b"),
    ("mentored", r"\bmentor(?:ed|ing|s)?\b"),
    ("headed", r"\bheaded\b"),
    ("managed a team", rf"\bmanag(?:e|ed|es|ing)\s+(?:a\s+|an\s+|the\s+)?(?:[\w-]+\s+){{0,2}}{_PEOPLE}\b"),
    ("directed a team", rf"\bdirect(?:ed|ing)\s+(?:a\s+|the\s+)?(?:[\w-]+\s+){{0,2}}{_PEOPLE}\b"),
    ("team of", r"\bteam of\b"),
]
LEADERSHIP_TITLE = re.compile(r"\b(?:lead|manager|head|director|principal|staff|supervisor|vp|chief)\b", re.IGNORECASE)


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


def _norm(token: str) -> str:
    token = token.lower().strip(".'\u2019-")
    for suffix in ("'s", "\u2019s"):
        if token.endswith(suffix):
            token = token[: -len(suffix)]
    return token


def _variants(token: str) -> set[str]:
    base = _norm(token)
    out = {base}
    if len(base) > 3 and base.endswith("s"):
        out.add(base[:-1])
    out.add(base + "s")
    return out


def _vocabulary(text: str) -> set[str]:
    """Every token (and hyphen part) of a text, normalized — the evidence vocabulary."""
    vocab: set[str] = set()
    for match in _TOKEN.finditer(text or ""):
        raw = match.group(0)
        for part in [raw, *raw.split("-")]:
            if part:
                vocab.add(_norm(part))
    return vocab


def _looks_like_entity(token: str, sentence_start: bool) -> bool:
    core = token.strip(".'\u2019-")
    if not core or _norm(core) in GENERIC_CAPS:
        return False
    if any(ch in core for ch in "#+") or re.search(r"[A-Za-z]\.[A-Za-z]", core) or core.startswith("."):
        return True                                     # C#, C++, Node.js, .NET
    if re.search(r"[A-Za-z]", core) and re.search(r"\d", core):
        return True                                     # EC2, S3, K8s
    if re.search(r"[a-z][A-Z]", core):
        return True                                     # GraphQL, TypeScript, iOS
    return core[0].isupper() and not sentence_start     # Rust, Go, Google (mid-sentence)


def new_entities(updated: str, original: str, scope: str, allowed: Iterable[str] = ()) -> list[str]:
    """Proper-noun-like tokens in ``updated`` that the original line and the
    evidence scope never mention (case-insensitive, plural/possessive tolerant).
    Hyphenated tokens are judged part by part ("Angular-based" -> "Angular")."""
    known = _vocabulary(original) | _vocabulary(scope) | {_norm(a) for a in allowed}
    found: list[str] = []
    for match in _TOKEN.finditer(updated or ""):
        raw = match.group(0)
        if _variants(raw) & known:
            continue
        sentence_start = bool(_SENTENCE_BREAK.search(updated[: match.start()]))
        parts = [p for p in raw.split("-") if p] if "-" in raw.strip("-") else [raw]
        for index, part in enumerate(parts):
            if not _looks_like_entity(part, sentence_start and index == 0) or _variants(part) & known:
                continue
            label = part.strip(".'\u2019-")
            if label and label not in found:
                found.append(label)
    return found


def _introduced(terms: Iterable[str], original: str, updated: str) -> list[str]:
    return [t for t in terms if contains_term(updated, t) and not contains_term(original, t)]


def check_change(change: dict, profile: dict, *, jd_keywords: Iterable[str] = (), job_title: str = "") -> list[str]:
    """Stage-2 reasons this change is not supported (empty list = OK).

    ``job_title`` words may appear in a *summary* rewrite ("… for Frontend
    Engineer roles") without counting as new entities; they still go through
    the skill, title and credential rules.
    """
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
    exp = None if target == "summary" else (_experience_for(profile, target) or {})
    if exp is not None:
        own_company = exp.get("company", "")
        for other in profile.get("experience") or []:
            company = other.get("company", "")
            if company and company != own_company and _introduced([company], original, updated):
                reasons.append(f'Mentions a different employer ("{company}").')

    # 6. New named entities (technologies, organizations, products, places).
    entity_scope = scope if exp is None else "\n".join(
        [scope, exp.get("company", ""), exp.get("title", ""), exp.get("location", "")])
    already = {r.split('"')[1].lower() for r in reasons if '"' in r}
    allowed = _vocabulary(job_title) if target == "summary" else set()
    for entity in new_entities(updated, original, entity_scope, allowed):
        if entity.lower() not in already:
            reasons.append(f'Introduces "{entity}", which is not supported by {scope_label} (possible invented technology, employer or claim).')

    # 7. Word-form metrics.
    scope_metrics = {m.lower() for m in WORD_METRIC.findall(scope)} | {m.lower() for m in WORD_METRIC.findall(original)}
    for word in dict.fromkeys(m.lower() for m in WORD_METRIC.findall(updated)):
        if word not in scope_metrics:
            reasons.append(f'Unsupported metric "{word}": not in the original line or its evidence.')

    # 8. Leadership / scope inflation.
    leadership_scope = "\n".join([original, scope] + ([exp.get("title", "")] if exp else
                                                     [e.get("title", "") for e in profile.get("experience") or []]))
    has_leadership_title = bool(LEADERSHIP_TITLE.search(leadership_scope))
    for label, pattern in LEADERSHIP:
        if re.search(pattern, updated, re.IGNORECASE) and not re.search(pattern, leadership_scope, re.IGNORECASE) \
                and not has_leadership_title:
            reasons.append(f'Scope inflation "{label}": no leadership evidence for {scope_label}.')

    return reasons


def validate_changes(raw_changes: list, profile: dict, *, jd_keywords: Iterable[str] = (),
                     evidence_checks: bool = True, job_title: str = "") -> ValidationResult:
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
        reasons = check_change(change, profile, jd_keywords=jd_keywords, job_title=job_title) if evidence_checks else []
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
