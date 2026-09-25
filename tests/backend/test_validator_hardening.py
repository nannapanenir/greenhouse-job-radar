"""Regression tests for the Phase 2 hardening review: general evidence-based
detection of invented technologies/organizations, word metrics and scope
inflation, without blocking ordinary rewording; plus server-side enforcement
at generation time."""

import copy
import json

import pytest

from backend.resume.apply import build_tailored_profile
from backend.resume.validator import check_change, correct_session_claims, new_entities, validate_changes

PROFILE = {
    "personalInformation": {"fullName": "Test Candidate"},
    "summary": {"text": "Frontend engineer building web apps with React and Angular.", "status": "extracted"},
    "skills": [{"name": s} for s in ["React", "Angular", "TypeScript", "JavaScript", "Java", "Spring Boot"]],
    "experience": [
        {"id": "exp-0", "company": "Acme", "title": "Software Engineer", "startDate": "Jan 2021", "endDate": "Present",
         "location": "Remote", "technologies": ["React", "Angular", "TypeScript", "JavaScript"],
         "bullets": [{"id": "exp-0-b0", "text": "Developed responsive applications using Angular and TypeScript."},
                     {"id": "exp-0-b1", "text": "Built admin applications in React."},
                     {"id": "exp-0-b2", "text": "Managed application state with component stores."}]},
        {"id": "exp-1", "company": "Globex", "title": "Developer", "startDate": "2018", "endDate": "2020",
         "location": "Austin, TX", "technologies": ["Java", "Spring Boot"],
         "bullets": [{"id": "exp-1-b0", "text": "Built backend services using Java."},
                     {"id": "exp-1-b1", "text": "Mentored two interns on Spring Boot conventions."}]},
    ],
    "education": [{"id": "edu-0", "degree": "B.S. Computer Science", "institution": "State University", "endDate": "2018"}],
    "certifications": [],
    "awards": [],
}
TEXT = {b["id"]: b["text"] for e in PROFILE["experience"] for b in e["bullets"]}
TEXT["summary"] = PROFILE["summary"]["text"]


def reasons(target, updated, **kw):
    return check_change({"targetBulletId": target, "original": TEXT[target], "updated": updated}, PROFILE, **kw)


# --- Must block -------------------------------------------------------------

@pytest.mark.parametrize("target, updated, needle", [
    ("exp-1-b0", "Built backend services using Java and Rust.", '"Rust"'),
    ("exp-1-b0", "Developed services using Go.", '"Go"'),
    ("exp-0-b1", "Built admin applications at Google.", '"Google"'),
    ("exp-0-b1", "Built admin applications in React for Microsoft Azure customers.", '"Microsoft"'),
    ("exp-0-b1", "Built admin applications in React and GraphQL.", '"GraphQL"'),
    ("exp-0-b1", "Built admin applications in React, deployed on Kubernetes.", '"Kubernetes"'),
    ("exp-0-b1", "Built admin applications in React hosted on EC2.", '"EC2"'),
    ("exp-0-b1", "Built admin applications in React and C#.", '"C#"'),
    ("summary", "Frontend engineer building web apps with React, Angular and Rust.", '"Rust"'),
])
def test_new_technologies_and_organizations_are_blocked(target, updated, needle):
    found = reasons(target, updated)
    assert found and needle in " ".join(found), found


@pytest.mark.parametrize("updated, needle", [
    ("Built admin applications in React, doubling adoption.", '"doubling"'),
    ("Built admin applications in React used by hundreds of analysts.", '"hundreds"'),
    ("Built admin applications in React, making releases twice as fast.", '"twice"'),
    ("Built admin applications in React with a tenfold speedup.", '"tenfold"'),
])
def test_word_metrics_are_blocked(updated, needle):
    assert needle in " ".join(reasons("exp-0-b1", updated))


@pytest.mark.parametrize("updated, needle", [
    ("Led a team of engineers building admin applications in React.", '"led"'),
    ("Built admin applications in React as part of a team of engineers.", '"team of"'),
    ("Spearheaded admin applications in React.", '"spearheaded"'),
    ("Built admin applications in React and managed a team of developers.", '"managed a team"'),
    ("Built admin applications in React while mentoring junior engineers.", '"mentored"'),
])
def test_scope_inflation_is_blocked(updated, needle):
    assert needle in " ".join(reasons("exp-0-b1", updated))


# --- Must allow (ordinary rewriting of existing evidence) -------------------

@pytest.mark.parametrize("target, updated", [
    ("exp-0-b0", "Built responsive Angular and TypeScript applications."),          # the example from the review
    ("exp-0-b0", "Developed responsive, Angular-based applications in TypeScript."),
    ("exp-0-b0", "Using Angular and TypeScript, developed responsive applications."),
    ("exp-0-b1", "Built React admin applications at Acme."),                        # own employer
    ("exp-0-b1", "Built admin applications and APIs in React."),                     # generic acronym
    ("exp-0-b2", "Managed application state with component stores in Angular."),    # technical "managed"
    ("exp-1-b1", "Mentored two interns on Spring Boot and Java conventions."),       # leadership already evidenced
    ("exp-1-b0", "Built backend services for Austin clients using Java."),           # role location
    ("summary", "Frontend engineer building web apps with React, Angular and TypeScript at Acme."),
])
def test_ordinary_rewording_is_allowed(target, updated):
    assert reasons(target, updated) == []


def test_job_title_words_allowed_only_in_summary():
    summary = "Frontend engineer building web apps with React and Angular, targeting Platform Engineer roles."
    assert reasons("summary", summary, job_title="Platform Engineer") == []
    assert reasons("summary", summary) != []
    assert reasons("exp-0-b1", "Built Platform admin applications in React.", job_title="Platform Engineer") != []


def test_entity_detection_is_plural_and_possessive_tolerant():
    assert new_entities("Acme's React dashboards", "", "Acme React dashboard") == []
    assert new_entities("Built it at Initech", "Built it", "") == ["Initech"]


# --- Enforcement: Accept All Safe / generation ------------------------------

def _session(*changes):
    return {"jobTitle": "Frontend Engineer", "keywords": [{"keyword": "GraphQL"}], "changes": list(changes)}


def test_generation_revalidates_accepted_changes():
    bad = {"id": "bad", "targetBulletId": "exp-1-b0", "original": TEXT["exp-1-b0"],
           "updated": "Built backend services using Java and Rust.", "status": "accepted"}
    good = {"id": "good", "targetBulletId": "exp-0-b0", "original": TEXT["exp-0-b0"],
            "updated": "Built responsive Angular and TypeScript applications.", "status": "accepted"}
    tailored, applied, skipped, overrides = build_tailored_profile(PROFILE, _session(bad, good))
    assert applied == ["good"] and overrides == []
    assert "failed evidence validation" in skipped[0] and "Rust" in skipped[0]
    assert "Rust" not in json.dumps(tailored)


def test_flagged_user_edit_needs_explicit_override_and_never_becomes_evidence():
    base = {"id": "e", "targetBulletId": "exp-0-b1", "original": TEXT["exp-0-b1"], "updated": TEXT["exp-0-b1"],
            "status": "edited", "editedText": "Built admin applications in React and GraphQL."}
    _, applied, skipped, _ = build_tailored_profile(PROFILE, _session(dict(base)))
    assert applied == [] and skipped                               # unflagged failing edit: not applied
    flagged = {**base, "userFlagged": ['Unsupported skill "GraphQL"']}
    tailored, applied, _, overrides = build_tailored_profile(PROFILE, _session(flagged))
    assert applied == ["e"] and overrides == ["e"]                 # explicit override: applied + reported
    assert "GraphQL" in json.dumps(tailored)
    assert "GraphQL" not in json.dumps(PROFILE)                    # master untouched
    # Future tailoring/validation still treats GraphQL as unsupported.
    again = validate_changes([{"targetBulletId": "exp-0-b0", "original": TEXT["exp-0-b0"],
                               "updated": "Developed responsive applications using Angular and GraphQL."}], PROFILE)
    assert again.blocked
    session = {"strongMatches": ["GraphQL"], "stillMissing": [], "keywords": []}
    correct_session_claims(session, PROFILE)
    assert [m["skill"] for m in session["stillMissing"]] == ["GraphQL"]


def test_profile_not_mutated_by_validation():
    before = copy.deepcopy(PROFILE)
    reasons("exp-1-b0", "Built backend services using Java and Rust at Google, doubling throughput.")
    assert PROFILE == before
