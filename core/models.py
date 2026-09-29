"""Plain data models shared by every stage of the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["high", "medium", "low"]
SEVERITY_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class Issue:
    """A problem found in the resume, with a concrete fix."""

    id: str
    severity: Severity
    section: str
    message: str
    fix: str
    example: str = ""


@dataclass
class ParsedResume:
    """Structured view of an uploaded resume."""

    raw_text: str
    sections: dict[str, str] = field(default_factory=dict)
    contact: dict[str, str] = field(default_factory=dict)
    bullets: list[str] = field(default_factory=list)
    page_count: int = 1
    has_tables: bool = False
    has_images: bool = False

    def has_section(self, *names: str) -> bool:
        return any(self.sections.get(n, "").strip() for n in names)


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    company: str
    location: str
    description: str


@dataclass
class ScoreBreakdown:
    total: int
    ats_format: float      # out of 25
    keyword_match: float   # out of 30
    content_quality: float # out of 25
    completeness: float    # out of 20
    explanation: str


@dataclass
class JobMatch:
    job: Job
    match_percent: int
    similarity: float
    skill_overlap: float
    matched: list[str]
    missing: list[str]
