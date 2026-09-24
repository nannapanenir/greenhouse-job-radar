import asyncio
import json

import pytest

from backend.models import CandidateProfile
from backend.resume.profile_extractor import ProfileExtractionError, extract_profile, sanitize_profile
from tests.backend.conftest import FakeProvider, load

RESPONSES = load("ai_profile_responses.json")


def test_structured_output_is_sanitized():
    profile = sanitize_profile(RESPONSES["ok"])
    assert profile["personalInformation"] == {
        "fullName": "Alex Rivera", "email": "alex.rivera@example.com", "phone": "(555) 010-2030",
        "location": "Jacksonville, FL", "linkedIn": "", "portfolio": "",
    }
    assert profile["skills"] == [{"name": "Angular", "status": "extracted"}, {"name": "TypeScript", "status": "extracted"}]
    csx, cgi = profile["experience"]
    assert csx["id"] == "exp-0" and csx["endDate"] == "Present"          # missing end date -> "Present" (reference)
    assert csx["technologies"] == ["Angular", "AWS"]
    assert [b["text"] for b in csx["bullets"]] == ["Built dashboards.", "Plain string bullet."]
    assert [b["id"] for b in csx["bullets"]] == ["exp-0-b0", "exp-0-b1"]
    assert cgi["id"] == "exp-1" and cgi["bullets"] == []                 # role without company dropped, ids stay dense
    assert profile["education"] == [{"id": "edu-0", "degree": "B.S. Computer Science", "institution": "University of Florida",
                                      "endDate": "2019", "status": "extracted"}]
    assert profile["certifications"][0]["year"] == ""                    # non-string year isn't coerced (reference)
    CandidateProfile.model_validate(profile)                             # valid API model


def test_wrapped_responses_parse_identically():
    assert sanitize_profile(RESPONSES["think_and_fences"]) == sanitize_profile(RESPONSES["ok"])
    assert sanitize_profile(RESPONSES["prose_around"]) == sanitize_profile(RESPONSES["ok"])


def test_missing_fields_stay_missing():
    profile = sanitize_profile(RESPONSES["missing_fields"])
    assert profile["personalInformation"]["fullName"] == "" and profile["summary"]["text"] == ""
    assert profile["experience"][0]["title"] == "" and profile["experience"][0]["bullets"] == []
    assert profile["skills"] == profile["education"] == profile["certifications"] == []


def test_string_skills_are_kept():
    assert [s["name"] for s in sanitize_profile(RESPONSES["string_skills"])["skills"]] == ["React", "Go"]


@pytest.mark.parametrize("key", ["malformed", "no_json", "array"])
def test_malformed_ai_responses_raise(key):
    with pytest.raises(ProfileExtractionError):
        sanitize_profile(RESPONSES[key])


def test_extract_profile_sends_resume_text_with_strict_prompt():
    provider = FakeProvider(RESPONSES["ok"])
    profile = asyncio.run(extract_profile(provider, "Alex Rivera\nCSX ..."))
    system, user = provider.calls[0]
    assert "Never invent employers" in system["content"] and "Alex Rivera\nCSX ..." in user["content"]
    assert profile["personalInformation"]["fullName"] == "Alex Rivera"
    assert json.loads(json.dumps(profile)) == profile
