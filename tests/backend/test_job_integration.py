"""Phase 1 Common Jobs (Greenhouse, Lever, Ashby) flow into Resume AI unchanged."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent import main as agent_main
from backend.main import app

AGENT_FIXTURES = Path(__file__).resolve().parents[1] / "agent" / "fixtures"
client = TestClient(app)


@pytest.fixture(scope="module")
def jobs_by_source():
    data = agent_main.run(sources_file=AGENT_FIXTURES / "sources.json", fixtures=AGENT_FIXTURES,
                          generated_at="2026-09-24T00:00:00Z")
    by_source = {}
    for job in data["jobs"]:
        by_source.setdefault(job["source"], job)
    return by_source


@pytest.mark.parametrize("source", ["greenhouse", "lever", "ashby"])
def test_common_job_reaches_resume_ai(source, jobs_by_source, profile):
    job = jobs_by_source[source]
    session = client.post("/api/resume/tailor", json={"candidateProfile": profile, "job": job, "mode": "balanced"})
    assert session.status_code == 200, session.text
    body = session.json()
    assert body["job"]["id"] == job["id"] and body["job"]["source"] == source
    assert body["job"]["applyUrl"] == job["applyUrl"] and body["jobTitle"] == (job["title"] or body["jobTitle"])
    assert (job["description"] or "")[:40] in body["jobDescriptionText"]
    assert job["company"] in body["jobDescriptionText"]
