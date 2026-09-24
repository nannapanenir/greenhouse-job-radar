import io
import zipfile

import pytest
from reportlab.pdfgen import canvas

from backend.resume.parser import MAX_FILE_BYTES, ResumeParseError, parse_document, parse_resume
from tests.backend.conftest import FIXTURES


def blank_pdf() -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.rect(50, 50, 100, 100)  # a drawing, no text layer (like a scanned page)
    pdf.save()
    return buffer.getvalue()


def test_pdf_extraction():
    doc = parse_resume("resume.PDF", (FIXTURES / "sample_resume.pdf").read_bytes(), "application/pdf")
    assert doc.file_type == "pdf" and doc.page_count == 1
    assert doc.text.startswith("Alex Rivera\n")
    assert "Built real-time rail operations dashboards in Angular used by 300+ dispatchers." in doc.text
    meta = doc.metadata()
    assert meta["sizeBytes"] > 0 and len(meta["sha256"]) == 64 and meta["textLength"] == len(doc.text)


def test_docx_extraction_includes_tables_in_order():
    doc = parse_resume("resume.docx", (FIXTURES / "sample_resume.docx").read_bytes())
    assert doc.file_type == "docx"
    lines = doc.text.split("\n")
    assert lines[0] == "Alex Rivera"
    assert lines.index("Skills") < lines.index("EXPERIENCE")  # table text kept in document order
    assert "Angular, TypeScript, React" in lines


@pytest.mark.parametrize("name", ["resume.txt", "resume.doc", "resume.png", "resume"])
def test_unsupported_types_rejected(name):
    with pytest.raises(ResumeParseError) as err:
        parse_resume(name, b"%PDF-1.4 whatever")
    assert err.value.code == "unsupported_type"


def test_signature_mismatch_rejected():
    with pytest.raises(ResumeParseError) as err:
        parse_resume("resume.pdf", b"<html>not a pdf</html>")
    assert err.value.code == "bad_signature" and "doesn't look like a real PDF" in str(err.value)
    with pytest.raises(ResumeParseError) as err:
        parse_resume("resume.docx", b"%PDF-1.4")
    assert err.value.code == "bad_signature"


def test_wrong_mime_rejected_but_generic_mime_allowed():
    data = (FIXTURES / "sample_resume.pdf").read_bytes()
    with pytest.raises(ResumeParseError) as err:
        parse_resume("resume.pdf", data, "image/png")
    assert err.value.code == "bad_mime"
    assert parse_resume("resume.pdf", data, "application/octet-stream").text


def test_empty_and_oversized_files():
    with pytest.raises(ResumeParseError) as err:
        parse_resume("resume.pdf", b"")
    assert err.value.code == "empty_file"
    with pytest.raises(ResumeParseError) as err:
        parse_resume("resume.pdf", b"%PDF-" + b"0" * MAX_FILE_BYTES)
    assert err.value.code == "too_large"


def test_malformed_files():
    with pytest.raises(ResumeParseError) as err:
        parse_resume("resume.pdf", b"%PDF-1.7\n this is garbage, not a pdf body")
    assert err.value.code == "malformed"
    with pytest.raises(ResumeParseError) as err:
        parse_resume("resume.docx", b"PK\x03\x04 truncated zip")
    assert err.value.code == "malformed"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", "no word/document.xml here")
    with pytest.raises(ResumeParseError) as err:
        parse_resume("resume.docx", buffer.getvalue())
    assert err.value.code == "malformed"


def test_image_only_pdf_is_not_ocrd():
    with pytest.raises(ResumeParseError) as err:
        parse_resume("scan.pdf", blank_pdf())
    assert err.value.code == "no_text" and "OCR is not supported" in str(err.value)


def test_job_description_text_files():
    doc = parse_document("jd.txt", "﻿Senior Engineer\r\nReact\r\n\r\n\r\n\r\nAWS".encode(), allowed=("pdf", "docx", "txt"))
    assert doc.text == "Senior Engineer\nReact\n\nAWS"
    with pytest.raises(ResumeParseError):
        parse_resume("jd.txt", b"text")  # resumes: PDF/DOCX only


def test_pdf_from_other_generators():
    # PDF produced by the standalone app's pdfkit generator (the Node parser's own output format)
    doc = parse_resume("resume.pdf", (FIXTURES / "sample_resume_pdfkit.pdf").read_bytes())
    assert doc.text.startswith("Alex Rivera") and "Software Engineer — CSX" in doc.text
