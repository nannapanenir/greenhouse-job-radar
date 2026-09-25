import json

import pytest
from fastapi.testclient import TestClient

from backend.api import resume as resume_api
from backend.main import app
from tests.backend.conftest import FIXTURES, FakeProvider, load, text

client = TestClient(app)


@pytest.fixture
def fake_ai(monkeypatch):
    provider = FakeProvider(text("ai_profile_responses.json") and load("ai_profile_responses.json")["ok"])
    monkeypatch.setattr(resume_api, "_provider", lambda: provider)
    return provider


def test_health_and_ai_status_never_leak_keys():
    assert client.get("/api/health").json()["status"] == "ok"
    saved = client.post("/api/ai/settings", json={"provider": "openrouter", "model": "m", "apiKey": "sk-or-LEAK"})
    assert saved.status_code == 200 and saved.json()["configured"]
    for path in ("/api/ai/status", "/api/health"):
        assert "sk-or-LEAK" not in client.get(path).text
    assert client.post("/api/ai/settings", json={"provider": "local", "model": "m"}).status_code == 400
    assert client.delete("/api/ai/settings").json()["configured"] is False


def test_env_managed_settings_are_read_only(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "local")
    monkeypatch.setenv("AI_MODEL", "llama")
    monkeypatch.setenv("LOCAL_AI_BASE_URL", "http://localhost:11434/v1")
    status = client.get("/api/ai/status").json()
    assert status == {**status, "configured": True, "provider": "local", "baseUrl": "http://localhost:11434/v1", "editable": False}
    assert client.post("/api/ai/settings", json={"provider": "openrouter", "model": "m", "apiKey": "k"}).status_code == 409


def test_parse_requires_ai_and_valid_files(fake_ai, monkeypatch):
    pdf = (FIXTURES / "sample_resume.pdf").read_bytes()
    response = client.post("/api/resume/parse", files={"file": ("resume.pdf", pdf, "application/pdf")})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile"]["personalInformation"]["fullName"] == "Alex Rivera"
    assert body["masterResume"]["fileType"] == "pdf" and body["masterResume"]["pageCount"] == 1
    assert "Built real-time rail operations" in fake_ai.calls[0][1]["content"]  # parser text reached the AI

    bad = client.post("/api/resume/parse", files={"file": ("resume.pdf", b"<html>", "application/pdf")})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "bad_signature"

    monkeypatch.setattr(resume_api, "_provider", lambda: None)
    docx_bytes = (FIXTURES / "sample_resume.docx").read_bytes()
    missing = client.post("/api/resume/parse", files={"file": ("r.docx", docx_bytes, "application/octet-stream")})
    assert missing.status_code == 400 and "not configured" in missing.json()["detail"]


def test_extract_text_for_job_descriptions():
    response = client.post("/api/resume/extract-text", files={"file": ("jd.txt", text("jd_frontend.txt").encode(), "text/plain")})
    assert response.status_code == 200 and response.json()["text"].startswith("Senior Frontend Engineer")


def test_analyze_tailor_check_generate_flow(profile):
    job = {"id": "greenhouse:acme:1", "source": "greenhouse", "company": "Acme Health", "title": "Senior Frontend Engineer",
           "description": text("jd_frontend.txt"), "applyUrl": "https://example.com/1"}
    analysis = client.post("/api/resume/analyze", json={"candidateProfile": profile, "job": job}).json()
    assert "GraphQL" in [m["skill"] for m in analysis["stillMissing"]] and analysis["matchBefore"] > 0

    session = client.post("/api/resume/tailor", json={"candidateProfile": profile, "job": job, "mode": "balanced"}).json()
    assert session["job"]["id"] == "greenhouse:acme:1" and session["source"] == "local" and session["changes"]
    assert all(isinstance(k["before"], int) for k in session["keywords"])  # 1, not 1.0

    change = {**session["changes"][0], "editedText": session["changes"][0]["original"] + " Using GraphQL."}
    check = client.post("/api/resume/check-change", json={"candidateProfile": profile, "change": change}).json()
    assert check == {"ok": False, "reasons": [check["reasons"][0]]} and "GraphQL" in check["reasons"][0]

    session["changes"][0]["status"] = "accepted"
    for fmt, magic, mime in [("docx", b"PK", "wordprocessingml"), ("pdf", b"%PDF", "application/pdf")]:
        file = client.post("/api/resume/generate", json={"candidateProfile": profile, "session": session, "format": fmt})
        assert file.status_code == 200 and file.content[:2] == magic[:2] and mime in file.headers["content-type"]
        assert file.headers["content-disposition"] == f'attachment; filename="Alex_Rivera_Senior_Frontend_Engineer_Resume.{fmt}"'
        assert file.headers["x-applied-changes"] == session["changes"][0]["id"]

    tailored = client.post("/api/resume/tailored-profile", json={"candidateProfile": profile, "session": session}).json()
    assert tailored["appliedChangeIds"] == [session["changes"][0]["id"]]


def test_tailor_validation_errors(profile):
    assert client.post("/api/resume/tailor", json={"candidateProfile": profile}).status_code == 400
    assert client.post("/api/resume/tailor", json={"candidateProfile": {"experience": [{"id": "x"}]},
                                                   "jobDescriptionText": "React"}).status_code == 422


def test_chat_endpoint(profile):
    reply = client.post("/api/resume/chat", json={"message": "Focus more on GraphQL", "candidateProfile": profile,
                                                  "jobDescriptionText": "React job"}).json()
    assert reply["operation"] == "adjust_tailoring" and "GraphQL isn't in your verified profile" in reply["reply"]


def test_jobs_endpoint(tmp_path, monkeypatch):
    from backend.api import system
    monkeypatch.setattr(system, "JOBS_FILE", tmp_path / "jobs.json")
    assert client.get("/api/jobs").status_code == 404
    (tmp_path / "jobs.json").write_text(json.dumps({"jobs": []}))
    assert client.get("/api/jobs").json() == {"jobs": []}
