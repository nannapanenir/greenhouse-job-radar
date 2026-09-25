"""Controlled Resume AI chat: map a message to ONE known operation.

Not an autonomous agent. Deterministic rules pick the operation; info
operations are answered here from the session; actions (analyze, tailor,
adjust, generate) are returned for the client to run through the normal
API endpoints, so every path stays validated and testable.
"""

from __future__ import annotations

import re
from typing import Optional

from .skills import contains_term, tech_lexicon
from .validator import profile_evidence

OPERATIONS = (
    "set_job_description", "analyze_job", "tailor_resume", "adjust_tailoring", "explain_change",
    "show_changes", "missing_skills", "generate_resume", "answer",
)

_JD_HINT = re.compile(r"responsibilit|requirement|qualification|years of experience", re.I)


def looks_like_job_description(text: str) -> bool:
    """Same heuristic as the standalone chat.js composer."""
    return len(text) > 200 or bool(_JD_HINT.search(text))


def _answer(text: str) -> str:
    """Port of chat.js answerQuestion canned answers."""
    lower = text.lower()
    if any(w in lower for w in ("score", "match", "percent")):
        return ('The match percentage is an "Estimated Resume Relevance" score — it\'s not the employer\'s actual ATS '
                "score. It's calculated from required/preferred skill coverage, responsibility alignment, and evidence "
                "strength, all traceable to your verified profile. See the Match Analysis tab for the full breakdown.")
    if "keyword" in lower:
        return ("Check the Keywords tab — it lists every job-description keyword, whether it's required or preferred, "
                "how many times it appears before/after tailoring, and whether it's verified in your profile.")
    if any(w in lower for w in ("export", "docx", "download")):
        return 'Once you\'ve reviewed the proposed changes, use "Generate DOCX" or "Generate PDF".'
    if any(w in lower for w in ("truth", "lie", "invent", "fake")):
        return ("I never invent skills, projects, certifications, achievements, or metrics, and I never change employer "
                "names, job titles, dates, or degrees. Every proposed change lists the exact evidence from your verified "
                "profile that supports it, and the server blocks any change it can't trace to that evidence.")
    return ("You can paste a job description here (or pick a job in Job Radar and click Tailor Resume) and I'll compare "
            "it to your verified career profile, propose truthful resume changes, and show you an explainable relevance score.")


def _change_label(change: dict, number: int) -> str:
    where = change.get("section", "")
    if change.get("company"):
        where += f" — {change['company']}"
    if change.get("bulletLabel"):
        where += f" | {change['bulletLabel']}"
    return f"{number}. {where}"


def _pick_change(text: str, session: dict, active_change_id: Optional[str]) -> Optional[tuple[int, dict]]:
    changes = session.get("changes") or []
    match = re.search(r"(?:change|bullet|#)\s*(\d+)", text, re.I)
    if match and 1 <= int(match.group(1)) <= len(changes):
        index = int(match.group(1)) - 1
        return index, changes[index]
    for index, change in enumerate(changes):
        if change.get("id") == active_change_id:
            return index, change
    return (0, changes[0]) if changes else None


def _focus_skills(text: str) -> list[str]:
    match = re.search(r"(?:focus|emphasi[sz]e|highlight)\s+(?:more\s+)?(?:on\s+)?(?:my\s+)?(.+)", text, re.I)
    if not match:
        return []
    phrase = re.sub(r"[.!?]+$", "", match.group(1)).strip()
    found = [t for t in tech_lexicon() if contains_term(phrase, t)]
    if not found and phrase:
        found = [p.strip() for p in re.split(r",|\band\b", phrase) if p.strip()][:3]
    # Keep the most specific term ("Angular 19" over "Angular").
    return [t for t in found if not any(o != t and t.lower() in o.lower() for o in found)]


def route_message(message: str, *, profile: Optional[dict] = None, session: Optional[dict] = None,
                  has_job: bool = False, active_change_id: Optional[str] = None) -> dict:
    """Returns {operation, reply, params}."""
    text = (message or "").strip()
    lower = text.lower()
    session = session or {}
    has_session = bool(session.get("changes") is not None and session.get("jobTitle"))

    def result(operation: str, reply: str, **params) -> dict:
        return {"operation": operation, "reply": reply, "params": params}

    if not text:
        return result("answer", _answer(""))

    if looks_like_job_description(text):
        return result("set_job_description", "Got it — tailoring against this job description.", jobDescriptionText=text)

    if re.search(r"\b(generate|download|export|final resume)\b", lower):
        fmt = "pdf" if "pdf" in lower else "docx"
        return result("generate_resume", f"Generating your tailored resume ({fmt.upper()}) with the changes you accepted.", format=fmt)

    if re.search(r"\bwhy\b.*\b(change|changed|bullet)\b|\bexplain\b", lower):
        if not has_session:
            return result("explain_change", "There are no proposed changes yet — tailor your resume for a job first.")
        picked = _pick_change(text, session, active_change_id)
        if not picked:
            return result("explain_change", "This session has no proposed changes to explain.")
        index, change = picked
        return result(
            "explain_change",
            f"{_change_label(change, index + 1)}\nReason: {change.get('reason') or '—'}\nEvidence: {change.get('evidence') or '—'}",
            changeId=change.get("id"),
        )

    if re.search(r"what (has )?changed|show( me)?( the)? changes|what did you change", lower):
        if not has_session:
            return result("show_changes", "Nothing has changed yet — tailor your resume for a job first.")
        changes = session.get("changes") or []
        if not changes:
            return result("show_changes", "No changes were proposed for this job.")
        lines = [f"{_change_label(c, i + 1)} [{c.get('status', 'pending')}]" for i, c in enumerate(changes)]
        blocked = len(session.get("blockedChanges") or [])
        tail = f"\n{blocked} AI suggestion(s) were blocked by the truth validator." if blocked else ""
        return result("show_changes", "Proposed changes:\n" + "\n".join(lines) + tail)

    if re.search(r"\bmissing\b|\bgaps?\b|skills? (do )?i (lack|need)", lower):
        if not has_session:
            return result("missing_skills", "Analyze a job first so I can compare its requirements to your profile.")
        missing = session.get("stillMissing") or []
        if not missing:
            return result("missing_skills", "Nothing required is missing — every extracted requirement is verified in your profile.")
        return result("missing_skills", "Not in your verified profile (I won't add these to your resume):\n"
                      + "\n".join(f"• {m['skill']}" for m in missing))

    focus = _focus_skills(text) if re.search(r"focus|emphasi[sz]e|highlight", lower) else []
    avoid = ["backend"] if re.search(r"backend[- ]heavy|less backend|not backend|no backend", lower) else []
    shorter = bool(re.search(r"summary.*(shorter|concise|brief|tighter)|(shorter|concise|brief).*summary", lower))
    mode = None
    if re.search(r"more conservative|less aggressive|minimal changes", lower):
        mode = "conservative"
    elif re.search(r"more aggressive|stronger|strong targeting", lower):
        mode = "strong"

    if focus or avoid or shorter or mode:
        if not has_job:
            return result("adjust_tailoring", "Pick or paste a job description first, then I can adjust the tailoring.")
        notes = []
        if focus and profile is not None:
            evidence = profile_evidence(profile)
            unverified = [f for f in focus if not contains_term(evidence, f)]
            focus = [f for f in focus if f not in unverified]
            if unverified:
                notes.append(f"{', '.join(unverified)} isn't in your verified profile, so I can't emphasize it.")
        if not (focus or avoid or shorter or mode):
            return result("adjust_tailoring", " ".join(notes) or "Nothing to adjust.")
        parts = []
        if focus:
            parts.append(f"emphasizing {', '.join(focus)}")
        if avoid:
            parts.append("keeping backend work in the background")
        if shorter:
            parts.append("shortening the summary")
        if mode:
            parts.append(f"switching to {mode} mode")
        reply = " ".join(notes + [f"Re-tailoring: {', '.join(parts)}."])
        return result("adjust_tailoring", reply, preferences={
            "focusSkills": focus, "avoidAreas": avoid, "summaryStyle": "shorter" if shorter else None,
        }, mode=mode)

    if re.search(r"\btailor\b|\boptimi[sz]e\b|rewrite my resume", lower):
        if not has_job:
            return result("tailor_resume", "Paste a job description or choose a job in Job Radar first.")
        return result("tailor_resume", "Tailoring your resume for this job…")

    if re.search(r"\banaly[sz]e\b|\bmy fit\b|how well|do i (fit|match)|am i a (good )?fit", lower):
        if not has_job:
            return result("analyze_job", "Paste a job description or choose a job in Job Radar first.")
        return result("analyze_job", "Analyzing your fit for this job…")

    return result("answer", _answer(text))
