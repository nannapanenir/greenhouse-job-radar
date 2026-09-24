import pytest

from backend.resume.chat import route_message

SESSION = {
    "jobTitle": "Frontend Engineer",
    "changes": [
        {"id": "c1", "section": "Experience", "company": "CSX", "bulletLabel": "Bullet 1", "reason": "R1", "evidence": "E1", "status": "accepted"},
        {"id": "c2", "section": "Summary", "company": "", "bulletLabel": "", "reason": "R2", "evidence": "E2", "status": "pending"},
    ],
    "stillMissing": [{"skill": "GraphQL", "note": ""}],
    "blockedChanges": [{"reasons": ["x"]}],
}


@pytest.mark.parametrize("message, operation", [
    ("Analyze my fit.", "analyze_job"),
    ("Tailor my resume for this job.", "tailor_resume"),
    ("Focus more on Angular.", "adjust_tailoring"),
    ("Focus more on React.", "adjust_tailoring"),
    ("Don't make me look backend-heavy.", "adjust_tailoring"),
    ("Make the summary shorter.", "adjust_tailoring"),
    ("Show me what changed.", "show_changes"),
    ("Why did you change this bullet?", "explain_change"),
    ("What skills am I missing?", "missing_skills"),
    ("Generate the final resume.", "generate_resume"),
    ("Is this my real ATS score?", "answer"),
    ("Requirements: " + "React " * 60, "set_job_description"),
])
def test_routing(message, operation, profile):
    assert route_message(message, profile=profile, session=SESSION, has_job=True)["operation"] == operation


def test_info_operations_answer_from_session(profile):
    assert "2. Summary [pending]" in route_message("Show me what changed", session=SESSION, has_job=True)["reply"]
    assert "1 AI suggestion(s) were blocked" in route_message("what changed?", session=SESSION, has_job=True)["reply"]
    explained = route_message("Why did you change change 2?", session=SESSION, has_job=True)
    assert "Reason: R2" in explained["reply"] and explained["params"]["changeId"] == "c2"
    assert route_message("explain", session=SESSION, has_job=True, active_change_id="c1")["params"]["changeId"] == "c1"
    assert "• GraphQL" in route_message("What skills am I missing?", session=SESSION, has_job=True)["reply"]


def test_adjust_params_and_truthfulness(profile):
    focus = route_message("Focus more on Angular", profile=profile, session=SESSION, has_job=True)
    assert focus["params"]["preferences"]["focusSkills"] == ["Angular"]
    backend = route_message("Don't make me look backend-heavy", profile=profile, has_job=True)
    assert backend["params"]["preferences"]["avoidAreas"] == ["backend"]
    short = route_message("Make the summary shorter", profile=profile, has_job=True)
    assert short["params"]["preferences"]["summaryStyle"] == "shorter"
    fake = route_message("Focus more on Kubernetes", profile=profile, has_job=True)
    assert fake["params"] == {} and "Kubernetes isn't in your verified profile" in fake["reply"]
    assert route_message("Generate the PDF", has_job=True)["params"] == {"format": "pdf"}


def test_needs_job_or_session():
    assert "first" in route_message("Tailor my resume", has_job=False)["reply"]
    assert "tailor your resume for a job first" in route_message("show me what changed", session={}, has_job=True)["reply"]
