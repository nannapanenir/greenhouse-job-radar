"""Runs scripts/resume-parity.mjs against the standalone Resume Tailor.

Skipped unless a resume-tailor checkout with node_modules is available:
    RESUME_TAILOR_REF=/path/to/resume-tailor python -m pytest tests/backend/test_resume_parity.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = [os.environ.get("RESUME_TAILOR_REF", ""), str(ROOT.parent / "resume-tailor"),
              str(ROOT.parent / "nannapanenir" / "resume-tailor")]
REFERENCE = next((Path(p) for p in CANDIDATES if p and (Path(p) / "node_modules" / "docx").exists()), None)


@pytest.mark.skipif(REFERENCE is None or shutil.which("node") is None,
                    reason="needs node + a resume-tailor checkout with `npm install` (set RESUME_TAILOR_REF)")
def test_resume_tailor_parity():
    result = subprocess.run(["node", "scripts/resume-parity.mjs", "--reference", str(REFERENCE)],
                            cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHON": sys.executable})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PARITY OK" in result.stdout
