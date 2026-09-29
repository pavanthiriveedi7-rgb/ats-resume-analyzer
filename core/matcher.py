"""Job loading and resume-to-JD matching (TF-IDF cosine + skill overlap)."""
from __future__ import annotations

import csv
import io
from collections import Counter
from pathlib import Path
from typing import BinaryIO

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Job, JobMatch
from .skills import DATA_DIR, extract_skills, load_skills

SIM_CEILING = 0.35   # TF-IDF cosine between a resume and a JD rarely exceeds this; used to rescale to 0-1
W_SIM, W_SKILL = 0.7, 0.3
ROLE_BONUS = 5
REQUIRED_COLUMNS = {"id", "title", "company", "location", "description"}
DEFAULT_JOBS = DATA_DIR / "jobs.csv"


def load_jobs(source: str | Path | bytes | BinaryIO | None = None) -> list[Job]:
    """Load jobs from a CSV path, raw bytes, or file object. Defaults to the bundled sample file."""
    if source is None:
        source = DEFAULT_JOBS
    if isinstance(source, (str, Path)):
        text = Path(source).read_text(encoding="utf-8-sig")
    elif isinstance(source, bytes):
        text = source.decode("utf-8-sig", errors="ignore")
    else:
        text = source.read().decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not REQUIRED_COLUMNS <= {f.strip().lower() for f in reader.fieldnames}:
        raise ValueError("Jobs CSV must have columns: " + ", ".join(sorted(REQUIRED_COLUMNS)))
    jobs = []
    for row in reader:
        row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        if row.get("description"):
            jobs.append(Job(row["id"], row["title"], row["company"], row["location"], row["description"]))
    return jobs


def market_demand(jobs: list[Job]) -> Counter[str]:
    """How many job descriptions mention each skill."""
    skills = load_skills()
    demand: Counter[str] = Counter()
    for job in jobs:
        demand.update(extract_skills(f"{job.title} {job.description}", skills))
    return demand


def rank_jobs(resume_text: str, resume_skills: set[str], jobs: list[Job], top_n: int = 10,
              role_hint: str = "") -> list[JobMatch]:
    """Rank jobs by 0.7 * text similarity + 0.3 * skill overlap (+ small bonus for a role match)."""
    if not resume_text.strip() or not jobs:
        return []
    skills = load_skills()
    docs = [resume_text] + [f"{j.title}. {j.description}" for j in jobs]
    matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True).fit_transform(docs)
    sims = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    role_tokens = {t for t in role_hint.lower().split() if len(t) > 2}

    matches: list[JobMatch] = []
    for job, sim in zip(jobs, sims):
        job_skills = extract_skills(f"{job.title} {job.description}", skills)
        matched = sorted(job_skills & resume_skills)
        missing = sorted(job_skills - resume_skills)
        overlap = len(matched) / len(job_skills) if job_skills else 0.0
        score = 100 * (W_SIM * min(1.0, float(sim) / SIM_CEILING) + W_SKILL * overlap)
        if role_tokens & set(job.title.lower().split()):
            score += ROLE_BONUS
        matches.append(JobMatch(job, round(min(100.0, score)), float(sim), overlap, matched, missing))
    matches.sort(key=lambda m: (-m.match_percent, -m.similarity))
    return matches[:top_n]


def skills_to_learn(matches: list[JobMatch], limit: int = 8) -> list[tuple[str, int]]:
    """Skills the resume lacks, ranked by how many of the matched jobs ask for them."""
    counts: Counter[str] = Counter()
    for m in matches:
        counts.update(m.missing)
    return counts.most_common(limit)
