"""End-to-end analysis: parse -> ATS -> skills -> match -> score -> suggestions."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .ats import ATSReport, run_ats_check
from .matcher import market_demand, rank_jobs, skills_to_learn
from .models import Job, JobMatch, ParsedResume, ScoreBreakdown, Issue
from .parser import parse_file, parse_text
from .scorer import score_resume
from .skills import extract_skills
from .suggestions import build_suggestions


@dataclass
class AnalysisResult:
    resume: ParsedResume
    ats: ATSReport
    score: ScoreBreakdown
    matches: list[JobMatch]
    demand: Counter[str]
    suggestions: list[Issue]
    skill_gaps: list[tuple[str, int]]
    resume_skills: set[str]


def _analyze(resume: ParsedResume, jobs: list[Job], role_hint: str) -> AnalysisResult:
    ats = run_ats_check(resume)
    have = extract_skills(resume.raw_text)
    demand = market_demand(jobs)
    matches = rank_jobs(resume.raw_text, have, jobs, role_hint=role_hint)
    gaps = skills_to_learn(matches)
    return AnalysisResult(
        resume=resume, ats=ats, score=score_resume(resume, ats.issues, have, demand), matches=matches,
        demand=demand, suggestions=build_suggestions(resume, ats.issues, gaps, len(matches)),
        skill_gaps=gaps, resume_skills=have)


def analyze(filename: str, data: bytes, jobs: list[Job], role_hint: str = "") -> AnalysisResult:
    return _analyze(parse_file(filename, data), jobs, role_hint)


def analyze_text(text: str, jobs: list[Job], role_hint: str = "", **layout: object) -> AnalysisResult:
    return _analyze(parse_text(text, **layout), jobs, role_hint)  # type: ignore[arg-type]
