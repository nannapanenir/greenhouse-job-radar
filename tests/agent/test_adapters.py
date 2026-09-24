from agent.adapters import AshbyAdapter, Company, GreenhouseAdapter, LeverAdapter


def by_id(result):
    return {job.source_job_id: job for job in result.jobs}


# --- Greenhouse -------------------------------------------------------------

def test_greenhouse_maps_existing_fields(transport):
    result = GreenhouseAdapter(transport).collect(Company("Anthropic", "anthropic"))
    assert result.ok and result.jobs_fetched == 5 and len(result.jobs) == 5

    job = by_id(result)["1001"]
    assert job.id == "greenhouse:anthropic:1001"
    assert job.company == "Anthropic" and job.company_key == "anthropic"
    assert job.title == "Applied AI Engineer"
    assert job.location == "San Francisco, CA"
    assert job.updated_at == "2026-09-23T10:15:00-04:00"   # verbatim, not reformatted
    assert job.posted_at == "2026-09-01T09:00:00-04:00"    # first_published
    assert job.apply_url == job.source_url == "https://job-boards.greenhouse.io/anthropic/jobs/1001"
    assert job.description.startswith("About the role\n\nYou'll build")
    assert job.metadata == {"internalJobId": 501, "requisitionId": "R-1001", "departments": ["Engineering"]}


def test_greenhouse_location_variants(transport):
    jobs = by_id(GreenhouseAdapter(transport).collect(Company("Anthropic", "anthropic")))
    assert jobs["1004"].location == "Remote - US"   # plain string location
    assert jobs["1003"].location is None            # {"name": ""} -> no location
    assert jobs["1004"].description == ""           # content: null


def test_greenhouse_missing_title_is_not_fabricated(transport):
    jobs = by_id(GreenhouseAdapter(transport).collect(Company("Databricks", "databricks")))
    assert jobs["3003"].title is None  # UI shows its own "Untitled Position" fallback


def test_greenhouse_http_error_is_recorded(transport):
    result = GreenhouseAdapter(transport).collect(Company("Notion", "notion"))
    assert not result.ok and result.error == "HTTP 404: Not Found" and result.jobs == []


# --- Lever ------------------------------------------------------------------

def test_lever_mapping(transport):
    result = LeverAdapter(transport).collect(Company("Palantir", "palantir"))
    assert result.ok and result.jobs_fetched == 4
    assert result.jobs_skipped == 1  # posting without id

    job = result.jobs[0]
    assert job.id == "lever:palantir:a1b2c3d4-0000-4000-8000-000000000001"
    assert job.title == "Forward Deployed Software Engineer"
    assert job.location == "New York, NY"
    assert job.posted_at == "2026-09-23T16:00:00.000Z"  # createdAt epoch ms -> ISO
    assert job.updated_at is None                        # Lever has no update time
    assert job.apply_url.endswith("/apply") and job.source_url.startswith("https://jobs.lever.co/palantir/")
    assert job.description == (
        "Work with customers to deploy software.\n\n"
        "What you'll do\n• Build data integrations\n• Ship & iterate\n\n"
        "Palantir is an equal opportunity employer."
    )
    assert job.metadata["allLocations"] == ["New York, NY", "Washington, D.C."]
    assert job.metadata["country"] == "US"


def test_lever_falls_back_to_html_description_and_hosted_url(transport):
    job = LeverAdapter(transport).collect(Company("Palantir", "palantir")).jobs[2]
    assert job.description == "HTML only & no plain text"
    assert job.apply_url == job.source_url  # no applyUrl in the posting


def test_lever_error_payload_is_a_failure(transport):
    result = LeverAdapter(transport).collect(Company("Spotify", "spotify"))
    assert not result.ok and result.error == "Document not found"


# --- Ashby ------------------------------------------------------------------

def test_ashby_mapping_and_unlisted_skip(transport):
    result = AshbyAdapter(transport).collect(Company("Ramp", "ramp"))
    assert result.ok and result.jobs_fetched == 4
    assert result.jobs_skipped == 1  # isListed: false
    assert "Hidden Role" not in [j.title for j in result.jobs]

    job = result.jobs[0]
    assert job.id == "ashby:ramp:5f0e1c2a-0000-4000-8000-00000000000a"
    assert job.title == "Software Engineer, Frontend"
    assert job.location == "New York, NY"
    assert job.posted_at == "2026-09-23T15:30:00.000+00:00" and job.updated_at is None
    assert job.apply_url.endswith("/application") and job.source_url.startswith("https://jobs.ashbyhq.com/ramp/")
    assert job.description == "Build Ramp's web app with React and TypeScript."
    assert job.metadata == {
        "isRemote": False, "workplaceType": "Hybrid", "employmentType": "FullTime",
        "department": "Engineering", "team": "Web",
        "secondaryLocations": ["San Francisco, CA"], "country": "United States",
    }


def test_ashby_html_description_fallback(transport):
    job = by_id(AshbyAdapter(transport).collect(Company("Ramp", "ramp")))["5f0e1c2a-0000-4000-8000-00000000000c"]
    assert job.description == "Role\n\nDetection & response"
    assert job.metadata["isRemote"] is True
