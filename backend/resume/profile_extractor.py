"""Raw resume text -> structured CandidateProfile via the AI provider.

Port of resume-tailor/server/profileExtractor.js. The prompt is unchanged;
``sanitize_profile`` keeps only well-formed fields the model returned and
never adds content (missing information stays empty).

Intentional difference: skills returned as plain strings (["React"]) are
kept; the Node version silently dropped them (common with local models).
"""

from __future__ import annotations

import logging
from typing import Any

from ..ai import AIProvider, complete_with_retry, extract_json_object
from .text import js_str

log = logging.getLogger("backend.resume")

SYSTEM_PROMPT = """You are a resume-parsing engine. You are given the raw extracted text of a candidate's resume. Extract ONLY information that is explicitly present in the text into a structured JSON career profile.

STRICT RULES (never violate):
- Never invent employers, job titles, dates, degrees, certifications, skills, or accomplishments that are not explicitly stated in the text.
- If a field is not present in the text, leave it as an empty string or empty array rather than guessing.
- Do not paraphrase or embellish bullet points; copy them close to verbatim, only cleaning up obvious extraction artifacts (stray line breaks, bullet characters).
- List each distinct technology/skill mentioned for a role in that role's "technologies" array, and also once in the top-level "skills" array.

Respond with ONLY a single JSON object, no markdown code fences, no prose before or after, matching exactly this shape:
{
  "personalInformation": {"fullName": string, "email": string, "phone": string, "location": string, "linkedIn": string, "portfolio": string},
  "summary": {"text": string},
  "skills": [{"name": string}],
  "experience": [{"company": string, "title": string, "startDate": string, "endDate": string, "location": string, "technologies": string[], "bullets": [{"text": string}]}],
  "education": [{"degree": string, "institution": string, "endDate": string}],
  "certifications": [{"name": string, "issuer": string, "year": string}]
}"""


class ProfileExtractionError(ValueError):
    pass


def build_user_prompt(resume_text: str) -> str:
    return (
        f"RESUME TEXT (raw extracted, may contain formatting artifacts):\n{resume_text}\n\n"
        "Respond with only the JSON object described in the system prompt."
    )


def _obj(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _arr(value: Any) -> list:
    return value if isinstance(value, list) else []


def sanitize_profile(raw: str) -> dict:
    try:
        parsed = extract_json_object(raw)
    except ValueError as error:
        log.error("[profile_extractor] Failed to parse AI response: %s", error)
        raise ProfileExtractionError("The AI response was not valid JSON. Check the server log for details.") from None
    if not isinstance(parsed, dict):
        raise ProfileExtractionError("The AI response was not a JSON object.")

    personal = _obj(parsed.get("personalInformation"))
    summary = _obj(parsed.get("summary"))

    skills = []
    for skill in _arr(parsed.get("skills")):
        name = js_str(skill) if isinstance(skill, str) else js_str(_obj(skill).get("name"))
        if name:
            skills.append({"name": name, "status": "extracted"})

    experience = []
    for entry in _arr(parsed.get("experience")):
        entry = _obj(entry)
        if not js_str(entry.get("company")):
            continue
        exp_id = f"exp-{len(experience)}"
        texts = [b if isinstance(b, str) else _obj(b).get("text") for b in _arr(entry.get("bullets"))]
        texts = [js_str(t) for t in texts if js_str(t)]
        experience.append({
            "id": exp_id,
            "company": js_str(entry.get("company")),
            "title": js_str(entry.get("title")),
            "startDate": js_str(entry.get("startDate")),
            "endDate": js_str(entry.get("endDate")) or "Present",
            "location": js_str(entry.get("location")),
            "status": "extracted",
            "technologies": [js_str(t) for t in _arr(entry.get("technologies")) if isinstance(t, str) and js_str(t)],
            "bullets": [{"id": f"{exp_id}-b{i}", "text": t, "status": "extracted"} for i, t in enumerate(texts)],
        })

    education = []
    for entry in _arr(parsed.get("education")):
        entry = _obj(entry)
        if not (js_str(entry.get("degree")) or js_str(entry.get("institution"))):
            continue
        education.append({
            "id": f"edu-{len(education)}", "degree": js_str(entry.get("degree")),
            "institution": js_str(entry.get("institution")), "endDate": js_str(entry.get("endDate")),
            "status": "extracted",
        })

    certifications = []
    for entry in _arr(parsed.get("certifications")):
        entry = _obj(entry)
        if not js_str(entry.get("name")):
            continue
        certifications.append({
            "id": f"cert-{len(certifications)}", "name": js_str(entry.get("name")),
            "issuer": js_str(entry.get("issuer")), "year": js_str(entry.get("year")), "status": "extracted",
        })

    return {
        "personalInformation": {
            key: js_str(personal.get(key))
            for key in ("fullName", "email", "phone", "location", "linkedIn", "portfolio")
        },
        "summary": {"text": js_str(summary.get("text")), "status": "extracted"},
        "skills": skills,
        "experience": experience,
        "education": education,
        "certifications": certifications,
        "awards": [],
    }


async def extract_profile(provider: AIProvider, resume_text: str) -> dict:
    content = await complete_with_retry(
        provider,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(resume_text)},
        ],
    )
    return sanitize_profile(content)
