import json

from agent.config import settings


def test_greenhouse_reuses_existing_app_config(monkeypatch, tmp_path):
    monkeypatch.delenv("GREENHOUSE_COMPANIES", raising=False)
    sources = settings.load_sources(tmp_path / "missing.json")
    existing = json.loads(settings.GREENHOUSE_CONFIG_FILE.read_text())
    assert [c.key for c in sources["greenhouse"]] == [c["token"] for c in existing]
    assert sources["lever"] == [] and sources["ashby"] == []


def test_greenhouse_env_var_takes_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("GREENHOUSE_COMPANIES", json.dumps([
        {"name": " Acme ", "token": " acme ", "enabled": True},
        {"name": "", "token": "bad", "enabled": True},          # invalid -> skipped
        {"name": "Off", "token": "off", "enabled": "yes"},      # invalid -> skipped
    ]))
    companies = settings.load_sources(tmp_path / "missing.json")["greenhouse"]
    assert [(c.name, c.key) for c in companies] == [("Acme", "acme")]


def test_default_sources_file_is_valid():
    sources = settings.load_sources()
    assert sources["lever"] and sources["ashby"]


def test_location_keywords_shared_with_frontend():
    keywords = settings.load_location_keywords()
    assert "United States" in keywords and len(keywords) > 300
