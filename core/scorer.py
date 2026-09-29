"""Resume scoring: ATS format 25 + keyword match 30 + content quality 25 + completeness 20."""
from __future__ import annotations

from collections import Counter

from .lexicon import ACTION_VERBS, METRIC_RE, WEAK_RE
from .models import Issue, ParsedResume, ScoreBreakdown

PENALTY = {"high": 6, "medium": 3, "low": 1}
TOP_MARKET_SKILLS = 25


def score_ats(issues: list[Issue]) -> float:
    return max(0.0, 25 - sum(PENALTY[i.severity] for i in issues))


def score_keywords(resume_skills: set[str], demand: Counter[str]) -> float:
    """Weighted share of the most demanded skills (across the job set) that the resume contains."""
    top = demand.most_common(TOP_MARKET_SKILLS)
    total = sum(c for _, c in top)
    if not total:
        return 15.0  # no jobs to compare against: neutral score
    return 30 * sum(c for s, c in top if s in resume_skills) / total


def score_content(resume: ParsedResume) -> float:
    bullets = resume.bullets
    if not bullets:
        return 5.0
    per_bullet = [
        0.5 * (b.split()[0].lower().strip(",.:;") in ACTION_VERBS) + 0.5 * bool(METRIC_RE.search(b))
        for b in bullets
    ]
    base = 25 * sum(per_bullet) / len(per_bullet)
    penalty = min(8, 1.5 * len(WEAK_RE.findall(resume.raw_text)))
    return max(0.0, base - penalty)


def score_completeness(resume: ParsedResume) -> float:
    c = resume.contact
    points = (
        4 * resume.has_section("skills") + 3 * resume.has_section("education")
        + 4 * resume.has_section("experience", "projects") + 2 * resume.has_section("summary")
        + 2 * ("email" in c) + 2 * ("phone" in c) + 2 * ("linkedin" in c or "github" in c)
        + 1 * resume.has_section("certifications", "projects")
    )
    return float(points)


def _explain(parts: dict[str, tuple[float, float]], total: int) -> str:
    weakest = min(parts, key=lambda k: parts[k][0] / parts[k][1])
    got, out_of = parts[weakest]
    band = "strong" if total >= 80 else "decent" if total >= 60 else "needs work"
    return (f"Your resume scores {total}/100, which is {band}. The weakest area is {weakest} "
            f"({got:.0f}/{out_of:.0f}); improving it will raise your score the most.")


def score_resume(resume: ParsedResume, issues: list[Issue], resume_skills: set[str],
                 demand: Counter[str]) -> ScoreBreakdown:
    ats = score_ats(issues)
    kw = score_keywords(resume_skills, demand)
    content = score_content(resume)
    comp = score_completeness(resume)
    total = round(ats + kw + content + comp)
    parts = {"ATS format": (ats, 25), "keyword match": (kw, 30), "content quality": (content, 25),
             "completeness": (comp, 20)}
    return ScoreBreakdown(total, round(ats, 1), round(kw, 1), round(content, 1), round(comp, 1),
                          _explain(parts, total))
