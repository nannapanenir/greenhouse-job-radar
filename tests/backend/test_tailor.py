import asyncio
import copy
import json

import pytest

from backend.ai import AIError
from backend.resume import fallback_engine, tailor
from tests.backend.conftest import FakeProvider, text

JD = text("jd_frontend.txt")
AI_RESPONSE = text("ai_tailor_response.json")


def run(coro):
    return asyncio.run(coro)


def test_ai_session_is_sanitized_validated_and_corrected(profile):
    provider = FakeProvider(AI_RESPONSE)
    session = run(tailor.tailor(profile, JD, "balanced", provider=provider))
    assert session["source"] == "ai" and session["provider"] == "fake" and session["model"] == "fake-model"
    assert session["matchBefore"] == 62                      # "61.5" -> Math.round -> 62
    assert [c["id"] for c in session["changes"]] == ["c1", "c10", "ai-7-exp-1-b0"]  # reference id numbering
    assert all(c["status"] == "pending" for c in session["changes"])
    assert session["changes"][2]["section"] == "Experience"  # non-string section defaulted
    assert len(session["blockedChanges"]) == 9
    assert "GraphQL" in [m["skill"] for m in session["stillMissing"]]
    assert "GraphQL" not in session["strongMatches"]
    docker = next(k for k in session["keywords"] if k["keyword"] == "Docker")
    assert (docker["before"], docker["after"], docker["status"], docker["location"]) == (0, 0, "Not found", "Not added")
    assert session["matchAfter"] == 68                       # 62 + (78-62) * 3/(3 kept + 5 evidence-blocked)
    assert any("lowered from 78% to 68%" in c for c in session["corrections"])
    system, user = provider.calls[0]
    assert "Never invent skills" in system["content"] and "TAILORING MODE: balanced." in user["content"]


def test_no_provider_uses_local_engine_with_warning(profile):
    session = run(tailor.tailor(profile, JD, "balanced"))
    assert session["source"] == "local" and "No AI provider configured" in session["warnings"][0]
    assert session["jobTitle"] == "Senior Frontend Engineer"


def test_ai_failure_falls_back_to_local_engine(profile):
    session = run(tailor.tailor(profile, JD, "balanced", provider=FakeProvider(AIError("down", retryable=False))))
    assert session["source"] == "local" and "Fake AI tailoring failed (down)" in session["warnings"][0]
    session = run(tailor.tailor(profile, JD, "balanced", provider=FakeProvider("not json at all")))
    assert session["source"] == "local" and "not valid JSON" in session["warnings"][0]


def test_modes(profile):
    jd = "Frontend Engineer\nRequirements: React, TypeScript, AWS, GraphQL, Docker.\nPreferred: Angular, Jest, Kubernetes."
    sessions = {m: run(tailor.tailor(profile, jd, m)) for m in ("conservative", "balanced", "strong")}
    keys = {m: [c["keywordsAdded"] for c in s["changes"]] for m, s in sessions.items()}
    assert keys["conservative"] == [["React"], ["TypeScript"]]
    assert keys["balanced"] == [["React"], ["TypeScript"]]  # preferred skills' bullets already used
    assert keys["strong"][-1] == ["React", "TypeScript", "AWS"] and sessions["strong"]["changes"][-1]["targetBulletId"] == "summary"
    assert sessions["conservative"]["matchAfter"] < sessions["balanced"]["matchAfter"] < sessions["strong"]["matchAfter"]


def test_missing_skill_is_never_added(profile):
    session = run(tailor.tailor(profile, JD, "strong"))
    assert "GraphQL" in [m["skill"] for m in session["stillMissing"]]
    assert all("graphql" not in c["updated"].lower() for c in session["changes"])


def test_master_profile_is_not_mutated(profile):
    before = copy.deepcopy(profile)
    run(tailor.tailor(profile, JD, "strong", provider=FakeProvider(AI_RESPONSE)))
    run(tailor.tailor(profile, JD, "strong"))
    assert profile == before


def test_job_contract_supplies_description_and_title(profile):
    job = {"id": "lever:acme:1", "source": "lever", "company": "Acme", "title": "Frontend Engineer",
           "location": "Remote", "description": "We use React and TypeScript daily."}
    text_ = tailor.job_description_for(job, None)
    assert text_.startswith("Frontend Engineer\nAcme\nRemote") and "React and TypeScript" in text_
    session = run(tailor.tailor(profile, text_, "balanced", job=job))
    assert session["job"]["source"] == "lever" and session["jobTitle"] == "Frontend Engineer"


def test_preferences(profile):
    jd = "Full Stack Engineer\nRequirements: Java, Spring Boot, React, TypeScript."
    base = run(tailor.tailor(profile, jd, "balanced"))
    assert [c["keywordsAdded"] for c in base["changes"]] == [["React"], ["TypeScript"]]
    # Focusing Java lets it claim the CGI bullet React would otherwise take...
    focus = run(tailor.tailor(profile, jd, "balanced", preferences={"focusSkills": ["Java"]}))
    assert [c["keywordsAdded"] for c in focus["changes"]] == [["Java"], ["TypeScript"]]
    # ...and "don't look backend-heavy" removes backend skills even when focused.
    avoid = run(tailor.tailor(profile, jd, "balanced", preferences={"focusSkills": ["Java"], "avoidAreas": ["backend"]}))
    assert [c["keywordsAdded"] for c in avoid["changes"]] == [["React"], ["TypeScript"]]
    short = run(tailor.tailor(profile, jd, "balanced", preferences={"summaryStyle": "shorter"}))
    summary = next(c for c in short["changes"] if c["targetBulletId"] == "summary")
    assert summary["updated"] == profile["summary"]["text"].split(". ")[0] + "."


def test_adjusted_after_score():
    session = {"matchBefore": 60, "matchAfter": 80, "changes": [{"status": "accepted"}, {"status": "rejected"},
                                                                 {"status": "edited"}, {"status": "pending"}]}
    assert fallback_engine.compute_adjusted_after_score(session) == 70
    assert fallback_engine.compute_adjusted_after_score({"matchBefore": 60, "matchAfter": 80, "changes": []}) == 60


@pytest.mark.parametrize("jd, title", [
    ("Senior Frontend Engineer\nReact", "Senior Frontend Engineer"),
    ("Platform Lead\r\nWe need a Lead Developer", "Platform Lead"),
    ("We are hiring!\nSoftware Engineer", "Untitled Role"),
])
def test_job_title_heuristic(jd, title):
    assert fallback_engine.analyze_job_description(jd)["jobTitle"] == title


def test_session_is_json_serializable(profile):
    json.dumps(run(tailor.tailor(profile, JD, "strong", provider=FakeProvider(AI_RESPONSE))))
