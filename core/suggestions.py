"""Turn ATS issues plus content analysis into one prioritised list of fixes."""
from __future__ import annotations

from .lexicon import ACTION_VERBS, METRIC_RE
from .models import SEVERITY_ORDER, Issue, ParsedResume


def build_suggestions(resume: ParsedResume, ats_issues: list[Issue],
                      skill_gaps: list[tuple[str, int]], n_jobs: int) -> list[Issue]:
    issues = list(ats_issues)
    bullets = resume.bullets

    if not bullets and not any(i.id == "garbled_text" for i in ats_issues):
        issues.append(Issue("no_bullets", "medium", "Experience", "No bullet points were detected.",
                            "Describe each project or role in 3-4 short bullets."))
    if bullets:
        unquantified = [b for b in bullets if not METRIC_RE.search(b)]
        ratio = len(unquantified) / len(bullets)
        if ratio >= 0.5:
            sample = unquantified[0]
            issues.append(Issue(
                "no_metrics", "high" if ratio >= 0.75 else "medium", "Experience",
                f"{len(unquantified)} of {len(bullets)} bullets have no number or measurable result.",
                "Add a number to each bullet: accuracy, speed, users, dataset size, or time saved. "
                "Only use figures that are true.",
                example=f'Before: "{sample}"\nAfter: "Built <what> using <tools>, achieving <number or %> <result>"'))
        weak_start = [b for b in bullets if b.split()[0].lower().strip(",.:;") not in ACTION_VERBS]
        if len(weak_start) / len(bullets) >= 0.5:
            issues.append(Issue(
                "weak_verbs", "low", "Experience",
                f"{len(weak_start)} of {len(bullets)} bullets don't start with an action verb.",
                "Start each bullet with a verb like Built, Designed, Automated, or Improved.",
                example=f'Before: "{weak_start[0]}"'))
    if skill_gaps:
        listing = ", ".join(f"{s} ({n}/{n_jobs} jobs)" for s, n in skill_gaps[:5])
        issues.append(Issue("skill_gap", "low", "Skills", f"Skills that top jobs ask for but your resume lacks: {listing}.",
                            "Add a skill only if you really have it. Otherwise, learn it through a small project first."))
    issues.sort(key=lambda i: SEVERITY_ORDER[i.severity])
    return issues
