"""Rule-based ATS-friendliness checks. Each rule is a small, independently testable function."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .lexicon import FIRST_PERSON_RE, UNUSUAL_BULLETS, WEAK_RE
from .models import SEVERITY_ORDER, Issue, ParsedResume

_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
          r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
DATE_STYLES = {
    "Month YYYY": re.compile(rf"\b{_MONTH}\.?\s+\d{{4}}\b", re.I),
    "MM/YYYY": re.compile(r"\b\d{1,2}/\d{4}\b"),
    "YYYY-MM": re.compile(r"\b\d{4}-\d{2}\b"),
}

Rule = Callable[[ParsedResume], list[Issue]]


@dataclass
class ATSReport:
    status: str  # pass | warn | fail
    issues: list[Issue]


def rule_garbled_text(r: ParsedResume) -> list[Issue]:
    text = r.raw_text
    letters = sum(c.isalnum() or c.isspace() for c in text)
    if len(text.strip()) < 200 or (text and letters / len(text) < 0.8):
        return [Issue("garbled_text", "high", "Format",
                      "Little or no readable text was extracted, so an ATS would see a nearly empty resume.",
                      "Export a text-based PDF or DOCX from Word or Google Docs instead of a scan or image.")]
    return []


def rule_tables_images(r: ParsedResume) -> list[Issue]:
    out = []
    if r.has_tables:
        out.append(Issue("tables", "high", "Format", "Tables or multi-column layouts can scramble reading order in an ATS.",
                         "Use a single-column layout with plain paragraphs and bullets."))
    if r.has_images:
        out.append(Issue("images", "medium", "Format", "Images, logos, or icons can't be read by an ATS.",
                         "Remove photos and graphics, and keep every detail as plain text."))
    return out


def rule_core_sections(r: ParsedResume) -> list[Issue]:
    out = []
    if not r.has_section("skills"):
        out.append(Issue("missing_skills", "high", "Skills", "No Skills section was detected.",
                         "Add a section titled exactly 'Skills' listing your tools and technologies."))
    if not r.has_section("education"):
        out.append(Issue("missing_education", "high", "Education", "No Education section was detected.",
                         "Add a section titled 'Education' with degree, college, and years."))
    if not r.has_section("experience", "projects"):
        out.append(Issue("missing_experience", "high", "Experience",
                        "No Experience or Projects section was detected.",
                        "Add 'Projects' or 'Internships' with 3-4 bullets each."))
    if not r.has_section("summary"):
        out.append(Issue("missing_summary", "low", "Summary", "No summary at the top.",
                         "Add a 2-line summary that names your target role and top skills."))
    return out


def rule_contact(r: ParsedResume) -> list[Issue]:
    out = []
    for key, label in (("email", "email address"), ("phone", "phone number")):
        if key not in r.contact:
            out.append(Issue(f"missing_{key}", "high", "Contact", f"No {label} was detected.",
                             f"Put your {label} in the body of the resume, not in a header or footer."))
    if "linkedin" not in r.contact and "github" not in r.contact:
        out.append(Issue("missing_links", "low", "Contact", "No LinkedIn or GitHub link found.",
                         "Add your LinkedIn and GitHub URLs; recruiters check them."))
    return out


def rule_date_formats(r: ParsedResume) -> list[Issue]:
    used = [name for name, rx in DATE_STYLES.items() if rx.search(r.raw_text)]
    if len(used) >= 2:
        return [Issue("date_formats", "low", "Format", f"Mixed date formats found ({', '.join(used)}).",
                      "Pick one format, such as 'Jun 2024', and use it everywhere.")]
    return []


def rule_length(r: ParsedResume) -> list[Issue]:
    if r.page_count > 2:
        return [Issue("too_long", "medium", "Format", f"The resume is about {r.page_count} pages long.",
                      "Trim to 1 page (students) or 2 pages (experienced) by cutting older or minor items.")]
    return []


def rule_unusual_bullets(r: ParsedResume) -> list[Issue]:
    found = sorted({c for c in r.raw_text if c in UNUSUAL_BULLETS})
    if found:
        return [Issue("odd_bullets", "low", "Format", f"Unusual bullet symbols found ({' '.join(found)}).",
                      "Use standard round bullets so the ATS reads them correctly.")]
    return []


def rule_first_person(r: ParsedResume) -> list[Issue]:
    hits = FIRST_PERSON_RE.findall(r.raw_text)
    if hits:
        return [Issue("first_person", "low", "Content", f"First-person words appear {len(hits)} time(s).",
                      "Start bullets with action verbs and drop 'I', 'my', and 'me'.")]
    return []


def rule_weak_phrases(r: ParsedResume) -> list[Issue]:
    found = sorted({m.group().lower() for m in WEAK_RE.finditer(r.raw_text)})
    if found:
        return [Issue("weak_phrases", "medium", "Content", f"Weak phrases found: {', '.join(found)}.",
                      "Replace them with strong verbs such as Built, Led, Automated, or Reduced.",
                      example='"Worked on a detection project" -> "Built a defect detection model using YOLO and OpenCV"')]
    return []


RULES: list[Rule] = [
    rule_garbled_text, rule_tables_images, rule_core_sections, rule_contact, rule_date_formats,
    rule_length, rule_unusual_bullets, rule_first_person, rule_weak_phrases,
]


def run_ats_check(resume: ParsedResume, rules: list[Rule] | None = None) -> ATSReport:
    issues = [i for rule in (rules or RULES) for i in rule(resume)]
    issues.sort(key=lambda i: SEVERITY_ORDER[i.severity])
    high = sum(i.severity == "high" for i in issues)
    medium = sum(i.severity == "medium" for i in issues)
    low = sum(i.severity == "low" for i in issues)
    status = "fail" if high else "warn" if (medium or low >= 3) else "pass"
    return ATSReport(status, issues)
