"""Regenerate tests/backend/fixtures/sample_resume.{pdf,docx} (committed).

    python scripts/make_resume_fixtures.py
"""

import io
from datetime import datetime, timezone
from pathlib import Path

import docx
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "tests" / "backend" / "fixtures"
LINES = [
    "Alex Rivera",
    "alex.rivera@example.com | (555) 010-2030 | Jacksonville, FL",
    "SUMMARY",
    "Frontend engineer with 5 years of experience building enterprise web applications with Angular and TypeScript.",
    "EXPERIENCE",
    "Software Engineer, CSX (Jan 2022 - Present)",
    "- Built real-time rail operations dashboards in Angular used by 300+ dispatchers.",
    "- Migrated legacy AngularJS modules to Angular and TypeScript, cutting bundle size by 35%.",
    "Associate Software Developer, CGI (Jun 2019 - Dec 2021)",
    "- Developed REST endpoints in Java and Spring Boot for a state benefits portal.",
    "EDUCATION",
    "B.S. Computer Science, University of Florida, 2019",
]


def make_pdf(path: Path) -> None:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER, invariant=1)
    y = 740
    for line in LINES:
        pdf.setFont("Helvetica-Bold" if line.isupper() or line == LINES[0] else "Helvetica", 11)
        pdf.drawString(54, y, line)
        y -= 18
    pdf.save()
    path.write_bytes(buffer.getvalue())


def make_docx(path: Path) -> None:
    document = docx.Document()
    for line in LINES[:4]:
        document.add_paragraph(line)
    table = document.add_table(rows=1, cols=2)  # resumes often use tables for skills
    table.cell(0, 0).text = "Skills"
    table.cell(0, 1).text = "Angular, TypeScript, React"
    for line in LINES[4:]:
        document.add_paragraph(line)
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)  # fixed so the file is reproducible
    document.core_properties.created = document.core_properties.modified = stamp
    document.save(path)


if __name__ == "__main__":
    make_pdf(OUT / "sample_resume.pdf")
    make_docx(OUT / "sample_resume.docx")
    print("wrote", OUT / "sample_resume.pdf", OUT / "sample_resume.docx")
