"""Python side of scripts/resume-parity.mjs: runs the ported functions on
the same inputs the Node reference gets. Reads a JSON list of requests on
stdin, writes a JSON list of results."""

import base64
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ai.base import extract_json_object  # noqa: E402
from backend.resume import fallback_engine, tailor  # noqa: E402
from backend.resume.docx_generator import build_resume_docx  # noqa: E402
from backend.resume.parser import parse_resume  # noqa: E402
from backend.resume.pdf_generator import build_resume_pdf  # noqa: E402
from backend.resume.profile_extractor import sanitize_profile  # noqa: E402

REFERENCE_SESSION_KEYS = ("jobTitle", "matchBefore", "matchAfter", "strongMatches", "stillMissing", "changes", "keywords")


def attempt(fn):
    try:
        return {"ok": True, "value": fn()}
    except Exception as error:  # noqa: BLE001 - report, don't crash the harness
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


def reference_session(raw, profile, evidence):
    session = tailor.sanitize_ai_session(raw, profile)
    session = tailor.finalize_session(session, profile, evidence_checks=evidence)
    out = {k: session[k] for k in REFERENCE_SESSION_KEYS}
    out["blocked"] = [b for b in session.get("blockedChanges", [])]
    return out


def fallback(jd, profile, mode, evidence):
    session = fallback_engine.build_session_from_jd(jd, profile, mode)
    session.pop("source", None)
    if evidence:
        session = tailor.finalize_session(session, profile, mode=mode)
        session = {k: session[k] for k in REFERENCE_SESSION_KEYS} | {"blocked": session["blockedChanges"]}
    return session


def document_text(data_b64, kind):
    data = base64.b64decode(data_b64)
    if kind == "pdf":
        import pymupdf
        with pymupdf.open(stream=data, filetype="pdf") as document:
            return "\n".join(page.get_text() for page in document)
    import docx
    return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)


def handle(request):
    op = request["op"]
    if op == "extract_json":
        return attempt(lambda: extract_json_object(request["raw"]))
    if op == "sanitize_profile":
        return attempt(lambda: sanitize_profile(request["raw"]))
    if op == "tailor_sanitize":
        return attempt(lambda: reference_session(request["raw"], request["profile"], request.get("evidence", False)))
    if op == "fallback":
        return attempt(lambda: fallback(request["jd"], request["profile"], request["mode"], request.get("evidence", False)))
    if op == "adjusted":
        return attempt(lambda: fallback_engine.compute_adjusted_after_score(request["session"]))
    if op == "parse":
        return attempt(lambda: parse_resume(request["filename"], base64.b64decode(request["data"])).text)
    if op == "generate":
        build = build_resume_pdf if request["format"] == "pdf" else build_resume_docx
        return attempt(lambda: base64.b64encode(build(request["profile"])).decode())
    if op == "document_text":
        return attempt(lambda: document_text(request["data"], request["kind"]))
    return {"ok": False, "error": f"unknown op {op}"}


if __name__ == "__main__":
    print(json.dumps([handle(r) for r in json.load(sys.stdin)]))
