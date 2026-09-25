"""Runs scripts/greenhouse-parity.mjs: existing JS Greenhouse flow vs Python agent."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    shutil.which("node") is None or not (ROOT / "node_modules" / "esbuild").exists(),
    reason="needs node and `npm install`",
)
def test_greenhouse_parity_with_existing_frontend():
    result = subprocess.run(
        ["node", "scripts/greenhouse-parity.mjs"],
        cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHON": sys.executable},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PARITY OK" in result.stdout
