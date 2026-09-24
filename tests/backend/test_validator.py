import copy

import pytest

from backend.resume.validator import check_change, correct_session_claims, validate_changes

CSX0 = "Built real-time rail operations dashboards in Angular used by 300+ dispatchers."
CSX1 = "Migrated legacy AngularJS modules to Angular and TypeScript, cutting bundle size by 35%."
CGI0 = "Developed REST endpoints in Java and Spring Boot for a state benefits portal."
SUMMARY = ("Frontend engineer with 5 years of experience building enterprise web applications with Angular and "
           "TypeScript. Focused on accessible, high-performance UIs.")


def change(target, original, updated, **extra):
    return {"id": "x", "targetBulletId": target, "original": original, "updated": updated, **extra}


def test_supported_rewrite_accepted(profile):
    ok = change("exp-0-b0", CSX0, "Built real-time rail operations dashboards in Angular and TypeScript, used by 300+ dispatchers.",
                keywordsAdded=["TypeScript"])
    result = validate_changes([ok], profile)
    assert result.accepted == [ok] and result.blocked == []


def test_unsupported_skill_rejected(profile):
    reasons = check_change(change("exp-0-b0", CSX0, CSX0.replace("Angular", "Angular and GraphQL")), profile)
    assert reasons == ['Unsupported skill "GraphQL": no evidence in CSX.']


def test_skill_must_be_evidenced_in_the_same_role(profile):
    # Java is a real skill, but from CGI — it can't be claimed on a CSX bullet.
    reasons = check_change(change("exp-0-b0", CSX0, CSX0, keywordsAdded=["Java"]), profile)
    assert reasons == ['Unsupported skill "Java": no evidence in CSX.']
    # ...while the summary may use anything verified anywhere in the profile.
    assert check_change(change("summary", SUMMARY, SUMMARY.replace("TypeScript.", "TypeScript, plus Java."), keywordsAdded=["Java"]), profile) == []


def test_employer_change_rejected(profile):
    reasons = check_change(change("exp-1-b0", CGI0, CGI0.replace("portal", "portal at CSX")), profile)
    assert reasons == ['Mentions a different employer ("CSX").']


def test_title_inflation_rejected(profile):
    reasons = check_change(change("exp-0-b1", CSX1, "As Senior Engineer, " + CSX1), profile)
    assert reasons == ['Title/seniority "Senior" was never one of your job titles.']


@pytest.mark.parametrize("target, original", [("startDate", "Jan 2022"), ("exp-0.title", "Software Engineer"),
                                              ("edu-0", "B.S. Computer Science"), ("cert-0", "AWS Certified Cloud Practitioner")])
def test_protected_fields_cannot_be_targeted(profile, target, original):
    result = validate_changes([change(target, original, "anything else")], profile)
    assert result.accepted == [] and "only bullets and the summary can change" in result.blocked[0]["reasons"][0]


def test_education_and_certification_claims_rejected(profile):
    reasons = check_change(change("exp-1-b0", CGI0, CGI0.replace(".", " while completing an MBA.")), profile)
    assert reasons == ['Credential claim "mba" is not in your education/certifications.']
    # an existing certification is fine in the summary
    assert check_change(change("summary", SUMMARY, SUMMARY + " AWS Certified Cloud Practitioner."), profile) == []


def test_fabricated_metric_and_years_rejected(profile):
    assert check_change(change("exp-0-b0", CSX0, CSX0.replace(".", ", cutting load time 40%.")), profile) == [
        'Unsupported number/metric "40": not in the original line or its evidence.']
    assert check_change(change("summary", SUMMARY, SUMMARY.replace("5 years", "8 years")), profile) == [
        'Unsupported number/metric "8": not in the original line or its evidence.']
    # a number already in the role's evidence is not fabricated
    assert check_change(change("exp-0-b0", CSX0, CSX0 + " Cut bundle size by 35%."), profile) == []


def test_original_must_match_verbatim(profile):
    result = validate_changes([change("exp-0-b0", CSX0 + " extra", "x"), change("exp-0-b0", f"  {CSX0} ", "Built dashboards in Angular.")], profile)
    assert len(result.blocked) == 1 and len(result.accepted) == 1  # trimmed comparison, like the reference


def test_missing_skill_remains_missing(profile):
    session = {
        "strongMatches": ["React", "TypeScript", "AWS", "GraphQL"],
        "stillMissing": [],
        "keywords": [{"keyword": k, "importance": "Required", "before": 1, "after": 2, "location": "Experience", "status": "Verified"}
                     for k in ["React", "TypeScript", "AWS", "GraphQL"]],
    }
    notes = correct_session_claims(session, profile)
    assert session["strongMatches"] == ["React", "TypeScript", "AWS"]
    assert [m["skill"] for m in session["stillMissing"]] == ["GraphQL"]
    graphql = session["keywords"][3]
    assert (graphql["status"], graphql["before"], graphql["after"]) == ("Not found", 0, 0)
    assert len(notes) == 2


def test_validator_does_not_mutate_profile(profile):
    before = copy.deepcopy(profile)
    validate_changes([change("exp-0-b0", CSX0, CSX0 + " GraphQL")], profile)
    assert profile == before
