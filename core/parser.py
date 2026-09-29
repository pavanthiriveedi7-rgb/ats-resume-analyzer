"""Resume parsing: PDF / DOCX / TXT bytes -> ParsedResume."""
from __future__ import annotations

import io
import math
import re
from pathlib import Path

from .lexicon import BULLET_RE
from .models import ParsedResume

MAX_BYTES = 5 * 1024 * 1024
SUPPORTED = {".pdf", ".docx", ".txt"}

_SECTION_PATTERNS: dict[str, str] = {
    "summary": r"(?:professional\s+)?(?:summary|profile|objective|career\s+objective|about\s+me)",
    "skills": r"(?:technical\s+|key\s+|core\s+)?skills(?:\s*(?:&|and)\s*tools)?|technologies|tech\s+stack",
    "experience": r"(?:work\s+|professional\s+|relevant\s+)?experience|employment(?:\s+history)?|internships?",
    "projects": r"(?:academic\s+|personal\s+|key\s+)?projects",
    "education": r"education(?:al)?(?:\s+qualifications?)?|academic\s+(?:background|qualifications?)",
    "certifications": r"certifications?(?:\s*(?:&|and)\s*courses)?|courses|licenses?",
    "achievements": r"achievements?|awards?(?:\s+and\s+honou?rs)?|honou?rs",
}
_HEADINGS = {k: re.compile(rf"^\s*(?:{v})\s*:?\s*$", re.I) for k, v in _SECTION_PATTERNS.items()}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
_LINKEDIN = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s|,;]+", re.I)
_GITHUB = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s|,;]+", re.I)


class ResumeParseError(ValueError):
    """Raised with a user-friendly message when a resume can't be read."""


def parse_file(filename: str, data: bytes) -> ParsedResume:
    """Validate and parse an uploaded resume."""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED:
        raise ResumeParseError("Unsupported file type. Upload a PDF, DOCX, or TXT file.")
    if len(data) > MAX_BYTES:
        raise ResumeParseError("That file is over 5 MB. Upload a smaller resume.")
    if not data:
        raise ResumeParseError("That file is empty.")
    try:
        if ext == ".pdf":
            return _read_pdf(data)
        if ext == ".docx":
            return _read_docx(data)
        return parse_text(data.decode("utf-8", errors="ignore"))
    except ResumeParseError:
        raise
    except Exception as exc:  # corrupt or password-protected files
        raise ResumeParseError("Couldn't read that file. It may be corrupted or password-protected.") from exc


def _read_pdf(data: bytes) -> ParsedResume:
    import pdfplumber

    parts: list[str] = []
    tables = images = False
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
            tables = tables or bool(page.find_tables())
            images = images or bool(page.images)
        pages = len(pdf.pages)
    return parse_text("\n".join(parts), page_count=pages, has_tables=tables, has_images=images)


def _read_docx(data: bytes) -> ParsedResume:
    import docx

    doc = docx.Document(io.BytesIO(data))
    lines = [p.text for p in doc.paragraphs]
    for table in doc.tables:  # keep table text so nothing is lost, but flag it for the ATS check
        for row in table.rows:
            lines.extend(cell.text for cell in row.cells)
    text = "\n".join(lines)
    return parse_text(text, has_tables=bool(doc.tables), has_images=bool(doc.inline_shapes))


def parse_text(text: str, page_count: int | None = None, has_tables: bool = False,
               has_images: bool = False) -> ParsedResume:
    """Split raw text into sections, contact details and bullets."""
    text = text.replace("\r", "")
    sections = split_sections(text)
    if page_count is None:
        page_count = max(1, math.ceil(len(text.split()) / 550))
    return ParsedResume(
        raw_text=text,
        sections=sections,
        contact=extract_contact(text),
        bullets=extract_bullets(text, sections),
        page_count=page_count,
        has_tables=has_tables,
        has_images=has_images,
    )


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.split("\n"):
        stripped = line.strip()
        heading = next((k for k, rx in _HEADINGS.items() if len(stripped) <= 45 and rx.match(stripped)), None)
        if heading:
            current = heading
            sections.setdefault(current, [])
        else:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def extract_contact(text: str) -> dict[str, str]:
    contact: dict[str, str] = {}
    if m := _EMAIL.search(text):
        contact["email"] = m.group()
    for m in _PHONE.finditer(text):
        if 10 <= len(re.sub(r"\D", "", m.group())) <= 13:
            contact["phone"] = m.group().strip()
            break
    if m := _LINKEDIN.search(text):
        contact["linkedin"] = m.group()
    if m := _GITHUB.search(text):
        contact["github"] = m.group()
    return contact


def extract_bullets(text: str, sections: dict[str, str]) -> list[str]:
    bullets = [BULLET_RE.sub("", ln).strip() for ln in text.split("\n") if BULLET_RE.match(ln)]
    if len(bullets) >= 2:
        return bullets
    fallback: list[str] = []  # un-bulleted resumes: use sentence-like lines in experience / projects
    for name in ("experience", "projects"):
        fallback += [ln.strip() for ln in sections.get(name, "").split("\n") if len(ln.split()) >= 6]
    return fallback


def guess_name(resume: ParsedResume) -> str:
    for line in resume.sections.get("header", "").split("\n"):
        line = line.strip()
        if line and "@" not in line and len(line) <= 50 and not re.search(r"\d{4}", line):
            return line
    return ""
