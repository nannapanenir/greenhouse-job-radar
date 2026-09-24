import json

import pytest

from agent import main as agent_main
from agent.adapters import Company, CompanyResult, JobAdapter, collect_all
from agent.adapters.base import FetchError
from agent.config.settings import load_location_keywords
from agent.models import Job
from agent.output import write_json
from agent.processing import clean_html_content, deduplicate_jobs, filter_jobs, sort_jobs


def job(job_id, **kw):
    return Job(source=kw.pop("source", "greenhouse"), source_job_id=job_id, company="Acme", company_key="acme", **kw)


# --- Failure isolation ------------------------------------------------------

class FlakyAdapter(JobAdapter):
    source = "lever"

    def board_url(self, company):
        return company.key

    def extract_postings(self, payload):
        return payload

    def map_job(self, raw, company):
        return Job(source="lever", source_job_id=raw["id"], company=company.name, company_key=company.key)


class FlakyTransport:
    def get_json(self, url, *, source, company_key):
        if company_key == "down":
            raise FetchError("request timeout")
        if company_key == "weird":
            raise KeyError("boom")  # unexpected error must not crash the run
        return [{"id": f"{company_key}-1"}]


def test_one_failed_company_does_not_stop_the_others():
    adapter = FlakyAdapter(FlakyTransport())
    tasks = [(adapter, Company(n, n)) for n in ("a", "down", "b", "weird", "c")]
    results = collect_all(tasks)

    assert [r.company.key for r in results] == ["a", "down", "b", "weird", "c"]  # order kept
    assert [r.ok for r in results] == [True, False, True, False, True]
    assert results[1].error == "request timeout"
    assert results[3].error == "unexpected error: KeyError"
    assert [j.id for r in results for j in r.jobs] == ["lever:a:a-1", "lever:b:b-1", "lever:c:c-1"]


# --- Filtering --------------------------------------------------------------

@pytest.mark.parametrize("location, kept", [
    ("San Francisco, CA", True), ("Remote - US", True), ("Boulder, CO", True), ("Remote (United States)", True),
    (None, True),  # no location -> kept (may be remote)
    ("London, UK", False), ("Toronto, ON", False), ("Remote", False), ("Campus Lead, Berlin", False),
])
def test_us_location_filter(location, kept):
    assert bool(filter_jobs([job("1", location=location)], load_location_keywords())) is kept


# --- Dedup / sort -----------------------------------------------------------

def test_deduplicate_by_apply_url_then_id_first_wins():
    jobs = [
        job("1", apply_url="https://x/1", title="first"),
        job("2", apply_url="https://x/1", title="same url"),
        job("1", apply_url="https://x/other", title="same id"),
        job("3", apply_url=None),
        job("3", apply_url=None),
    ]
    assert [j.title for j in deduplicate_jobs(jobs)] == ["first", None]
    assert [j.source_job_id for j in deduplicate_jobs(jobs)] == ["1", "3"]


def test_sort_newest_first_across_timezones_and_providers():
    jobs = [
        job("old", updated_at="2026-09-20T10:00:00Z"),
        job("undated"),
        job("lever", source="lever", posted_at="2026-09-23T16:00:00.000Z"),
        job("tz", updated_at="2026-09-23T10:15:00-04:00"),   # 14:15Z
        job("tie-a", updated_at="2026-09-21T00:00:00Z"),
        job("tie-b", updated_at="2026-09-21T00:00:00Z"),
    ]
    assert [j.source_job_id for j in sort_jobs(jobs)] == ["lever", "tz", "tie-a", "tie-b", "old", "undated"]


def test_clean_html_matches_legacy_behaviour():
    assert clean_html_content(None) == ""
    assert clean_html_content("&lt;p&gt;A &amp;amp; B&lt;/p&gt;&lt;ul&gt;&lt;li&gt;x&lt;/li&gt;&lt;/ul&gt;") == "A &amp; B\n\n• x"
    assert clean_html_content("x &#x1F600; y") == "x  y"  # JS fromCharCode truncation


# --- End to end -------------------------------------------------------------

def test_run_on_fixtures_produces_combined_output(fixtures_dir):
    data = agent_main.run(sources_file=fixtures_dir / "sources.json", fixtures=fixtures_dir,
                          generated_at="2026-09-24T00:00:00Z")
    assert data["generatedAt"] == "2026-09-24T00:00:00Z"
    assert data["statistics"] == {
        "companiesSearched": 9, "successfulCompanies": 6, "failedCompanies": 3, "jobsScanned": 19,
        "jobsAfterFilters": 13, "duplicatesRemoved": 1, "jobsKept": 12,
    }
    assert {s: v["jobs"] for s, v in data["sources"].items()} == {"greenhouse": 8, "lever": 2, "ashby": 2}
    assert {(f["source"], f["key"]) for f in data["failures"]} == {
        ("greenhouse", "notion"), ("lever", "spotify"), ("ashby", "linear")}
    assert "disabledco" not in {c["key"] for c in data["companies"]}
    assert len({j["id"] for j in data["jobs"]}) == len(data["jobs"])
    assert len({j["applyUrl"] for j in data["jobs"]}) == len(data["jobs"])
    # deterministic: same input -> same output
    again = agent_main.run(sources_file=fixtures_dir / "sources.json", fixtures=fixtures_dir,
                           generated_at="2026-09-24T00:00:00Z")
    assert json.dumps(again) == json.dumps(data)


def test_all_failed_does_not_overwrite_existing_output(tmp_path, fixtures_dir):
    out = tmp_path / "jobs.json"
    out.write_text('{"keep": true}')
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"greenhouse": [{"name": "Nope", "token": "nope", "enabled": True}]}))
    code = agent_main.main(["--fixtures", str(fixtures_dir), "--sources", str(sources), "--output", str(out), "-q"])
    assert code == 1 and json.loads(out.read_text()) == {"keep": True}


def test_main_writes_output_file(tmp_path, fixtures_dir):
    out = tmp_path / "data" / "jobs.json"
    code = agent_main.main(["--fixtures", str(fixtures_dir), "--sources", str(fixtures_dir / "sources.json"),
                            "--output", str(out), "-q"])
    assert code == 0 and json.loads(out.read_text())["statistics"]["jobsKept"] == 12


def test_write_json_is_atomic(tmp_path):
    out = tmp_path / "jobs.json"
    write_json({"a": "é"}, out)
    assert json.loads(out.read_text(encoding="utf-8")) == {"a": "é"}
    assert [p.name for p in tmp_path.iterdir()] == ["jobs.json"]  # no temp files left
    assert out.stat().st_mode & 0o777 == 0o644
