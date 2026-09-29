"""Build an ATS-safe resume from what the candidate already wrote. Never invents facts."""
from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from .lexicon import BULLET_RE
from .models import Job, ParsedResume
from .parser import guess_name
from .skills import extract_skills, load_skills

SECTION_ORDER = [("summary", "Summary"), ("skills", "Skills"), ("experience", "Experience"),
                 ("projects", "Projects"), ("education", "Education"),
                 ("certifications", "Certifications"), ("achievements", "Achievements")]


@dataclass
class Section:
    title: str
    blocks: list[tuple[str, str]]  # ("p" | "b", text)


@dataclass
class GeneratedResume:
    name: str
    contact_line: str
    sections: list[Section]
    change_log: list[str] = field(default_factory=list)
    skills_to_learn: list[str] = field(default_factory=list)


def _blocks(text: str) -> list[tuple[str, str]]:
    out = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        out.append(("b", BULLET_RE.sub("", line).strip()) if BULLET_RE.match(line) else ("p", line.strip()))
    return out


def build_resume(resume: ParsedResume, demand: Counter[str], job: Job | None = None) -> GeneratedResume:
    """Reorder and clean the resume for the whole job set (master) or one job (tailored)."""
    skills = load_skills()
    have = extract_skills(resume.raw_text, skills)
    wanted = extract_skills(f"{job.title} {job.description}", skills) if job else set()
    log: list[str] = []

    def rank(skill: str) -> tuple[int, int]:
        return (0 if skill in wanted else 1, -demand.get(skill, 0))

    sections: list[Section] = []
    summary = resume.sections.get("summary", "").strip()
    ordered = sorted(have, key=rank)
    if summary:
        blocks = _blocks(summary)
    elif ordered:
        blocks = [("p", f"Motivated candidate with hands-on experience in {', '.join(ordered[:3])}.")]
        log.append("Added a starter summary built only from skills already in your resume. Edit it in your own words.")
    else:
        blocks = []
    if job:
        blocks.insert(0, ("p", f"Target role: {job.title}"))
        log.append(f"Tailored for: {job.title} at {job.company}.")
    if blocks:
        sections.append(Section("Summary", blocks))

    skills_text = resume.sections.get("skills", "")
    if skills_text.strip():
        tokens: list[str] = []
        for chunk in re.split(r"[,;|•\n]", skills_text):
            tok = chunk.split(":")[-1].strip(" -–—*")
            if tok and tok.lower() not in {t.lower() for t in tokens}:
                tokens.append(tok)
        keyed = sorted(enumerate(tokens), key=lambda p: (min((rank(s) for s in extract_skills(p[1], skills)),
                                                             default=(2, 0)), p[0]))
        skill_line = ", ".join(t for _, t in keyed)
        log.append("Reordered your skills so the most in-demand ones come first (nothing added or removed).")
    else:
        skill_line = ", ".join(ordered)
        if skill_line:
            log.append("Created a Skills section from skills found elsewhere in your resume.")
    if skill_line:
        sections.append(Section("Skills", [("p", skill_line)]))

    for key, title in SECTION_ORDER:
        if key in ("summary", "skills"):
            continue
        text = resume.sections.get(key, "")
        if text.strip():
            sections.append(Section(title, _blocks(text)))

    log += ["Used a single-column layout with standard section headings.",
            "Standardised all bullets to plain round bullets.",
            "Kept your experience, projects, and education wording exactly as written."]
    pool = wanted if job else {s for s, _ in demand.most_common(25)}
    learn = sorted(pool - have, key=lambda s: -demand.get(s, 0))[:8]

    contact_line = " | ".join(v for k in ("email", "phone", "linkedin", "github") if (v := resume.contact.get(k)))
    return GeneratedResume(guess_name(resume) or "Your Name", contact_line, sections, log, learn)


def to_docx(gen: GeneratedResume) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt, RGBColor

    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Inches(0.8)
        s.top_margin = s.bottom_margin = Inches(0.7)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(10.5)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(gen.name)
    run.bold, run.font.size = True, Pt(18)
    if gen.contact_line:
        contact = doc.add_paragraph(gen.contact_line)
        contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for sec in gen.sections:
        heading = doc.add_heading(sec.title.upper(), level=2)
        for r in heading.runs:
            r.font.color.rgb, r.font.size, r.font.name = RGBColor(0, 0, 0), Pt(12), "Calibri"
        for kind, text in sec.blocks:
            doc.add_paragraph(text, style="List Bullet" if kind == "b" else None)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def to_pdf(gen: GeneratedResume) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    def safe(t: str) -> str:  # base-14 fonts only cover cp1252
        return escape(t.encode("cp1252", "replace").decode("cp1252"))

    base = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=base["Title"], fontSize=18, spaceAfter=2)
    center = ParagraphStyle("c", parent=base["Normal"], alignment=1, fontSize=9.5)
    head = ParagraphStyle("h", parent=base["Heading2"], fontSize=11.5, spaceBefore=10, spaceAfter=3)
    body = ParagraphStyle("b", parent=base["Normal"], fontSize=10, leading=13)

    story = [Paragraph(safe(gen.name), title)]
    if gen.contact_line:
        story.append(Paragraph(safe(gen.contact_line), center))
    for sec in gen.sections:
        story.append(Paragraph(safe(sec.title.upper()), head))
        pending: list[ListItem] = []

        def flush() -> None:
            if pending:
                story.append(ListFlowable(list(pending), bulletType="bullet", start="•", leftIndent=14))
                pending.clear()

        for kind, text in sec.blocks:
            if kind == "b":
                pending.append(ListItem(Paragraph(safe(text), body)))
            else:
                flush()
                story.append(Paragraph(safe(text), body))
        flush()
    story.append(Spacer(1, 4))
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=16 * mm, bottomMargin=16 * mm).build(story)
    return buf.getvalue()
