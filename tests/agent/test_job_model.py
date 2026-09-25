import pytest

from agent.models import Job, build_job_id


def make(**overrides):
    fields = dict(source="greenhouse", source_job_id=123, company="Acme", company_key="acme")
    fields.update(overrides)
    return Job(**fields)


def test_global_id_is_source_company_and_job_id():
    job = make()
    assert job.id == "greenhouse:acme:123" == build_job_id("greenhouse", "acme", "123")
    assert job.source_job_id == "123"  # always a string


@pytest.mark.parametrize("field", ["source_job_id", "company", "company_key"])
def test_required_fields(field):
    with pytest.raises(ValueError):
        make(**{field: ""})


def test_unknown_source_rejected():
    with pytest.raises(ValueError):
        make(source="linkedin")


def test_serializes_to_camel_case_in_stable_order():
    data = make(title="Engineer", apply_url="https://x/1", metadata={"a": 1}).to_dict()
    assert list(data) == [
        "id", "source", "sourceJobId", "company", "companyKey", "title", "location", "description",
        "postedAt", "updatedAt", "applyUrl", "sourceUrl", "matchedKeywords", "metadata",
    ]
    assert data["applyUrl"] == "https://x/1"
    assert data["matchedKeywords"] == [] and data["location"] is None
