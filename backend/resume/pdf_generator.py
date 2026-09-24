"""Tailored profile -> ATS-friendly PDF (port of pdfGenerator.js, ReportLab).

Single column, real (selectable) text, standard Helvetica fonts, US Letter
with 54pt margins — the same layout as the Node/pdfkit version.
"""

from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

GREY = HexColor("#444444")

STYLES = {
    "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=18, leading=22),
    "contact": ParagraphStyle("contact", fontName="Helvetica", fontSize=10, leading=13, textColor=GREY, spaceBefore=3),
    "heading": ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=13, leading=16, spaceBefore=12, spaceAfter=3),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=11, leading=14),
    "role": ParagraphStyle("role", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=6),
    "dates": ParagraphStyle("dates", fontName="Helvetica-Oblique", fontSize=10, leading=13, textColor=GREY, spaceAfter=2),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=11, leading=14, leftIndent=20, bulletIndent=10),
}


def _p(text: str, style: str) -> Paragraph:
    return Paragraph(escape(text or ""), STYLES[style])


def build_resume_pdf(profile: dict) -> bytes:
    personal = profile.get("personalInformation") or {}
    flow = [_p(personal.get("fullName") or "", "name")]

    contact = "  |  ".join(v for v in (personal.get("email"), personal.get("phone"), personal.get("location"), personal.get("linkedIn")) if v)
    if contact:
        flow.append(_p(contact, "contact"))

    def heading(text: str) -> None:
        flow.append(_p(text, "heading"))

    summary = (profile.get("summary") or {}).get("text")
    if summary:
        heading("Summary")
        flow.append(_p(summary, "body"))

    skills = profile.get("skills") or []
    if skills:
        heading("Skills")
        flow.append(_p(", ".join(s.get("name", "") for s in skills), "body"))

    experience = profile.get("experience") or []
    if experience:
        heading("Experience")
        for exp in experience:
            flow.append(_p(f"{exp.get('title') or ''} — {exp.get('company') or ''}", "role"))
            date_line = "  |  ".join(v for v in (f"{exp.get('startDate') or ''} - {exp.get('endDate') or ''}", exp.get("location")) if v)
            if date_line.strip():
                flow.append(_p(date_line, "dates"))
            for bullet in exp.get("bullets") or []:
                flow.append(Paragraph(escape(bullet.get("text", "")), STYLES["bullet"], bulletText="•"))

    education = profile.get("education") or []
    if education:
        heading("Education")
        for edu in education:
            end = f" ({edu['endDate']})" if edu.get("endDate") else ""
            flow.append(_p(f"{edu.get('degree') or ''}, {edu.get('institution') or ''}{end}", "body"))

    certifications = profile.get("certifications") or []
    if certifications:
        heading("Certifications")
        for cert in certifications:
            flow.append(_p(" — ".join(v for v in (cert.get("name"), cert.get("issuer"), cert.get("year")) if v), "body"))

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=LETTER, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54,
        title=f"{personal.get('fullName') or 'Candidate'} — Resume", author=personal.get("fullName") or "",
    )
    document.build(flow or [Spacer(1, 1)])
    return buffer.getvalue()
