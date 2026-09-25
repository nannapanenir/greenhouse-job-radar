import json
from pathlib import Path

import pytest

from backend.ai.base import AIError, AIProvider

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeProvider(AIProvider):
    """Returns canned replies in order (or raises AIError instances)."""

    name = "fake"
    label = "Fake AI"

    def __init__(self, *replies, model: str = "fake-model"):
        super().__init__(model)
        self.replies = list(replies)
        self.calls: list[list[dict]] = []

    async def complete(self, messages, *, temperature=0.1, timeout=60.0):
        self.calls.append(messages)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def profile() -> dict:
    return load("profile.json")


@pytest.fixture(autouse=True)
def isolated_ai_settings(tmp_path, monkeypatch):
    """Never read/write the developer's real settings or env keys in tests."""
    monkeypatch.setenv("RESUME_AI_DATA_DIR", str(tmp_path / "data"))
    for var in ("AI_PROVIDER", "AI_MODEL", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "LOCAL_AI_BASE_URL", "LOCAL_AI_API_KEY"):
        monkeypatch.delenv(var, raising=False)


__all__ = ["AIError", "FIXTURES", "FakeProvider", "load", "text"]
