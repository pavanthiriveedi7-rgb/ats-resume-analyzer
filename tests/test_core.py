import pytest

from core.ats import run_ats_check
from core.generator import build_resume, to_docx, to_pdf
from core.llm import no_new_facts
from core.matcher import load_jobs, rank_jobs
from core.models import ParsedResume
from core.parser import ResumeParseError, parse_file, parse_text
from core.pipeline import analyze, analyze_text
from core.skills import extract_skills


def ids(report):
    return {i.id for i in report.issues}


# ---------- parser ----------
def test_parser_sections_and_contact(good_text):
    r = parse_text(good_text)
    assert {"summary", "skills", "projects", "education"} <= {k for k, v in r.sections.items() if v}
    assert r.contact["email"] == "ravi.kumar@example.com"
    assert "98765" in r.contact["phone"]
    assert "github" in r.contact and "linkedin" in r.contact
    assert len(r.bullets) == 3


def test_parser_rejects_bad_files():
    with pytest.raises(ResumeParseError):
        parse_file("resume.exe", b"x")
    with pytest.raises(ResumeParseError):
        parse_file("resume.pdf", b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(ResumeParseError):
        parse_file("resume.pdf", b"not a pdf")


# ---------- skills ----------
def test_skill_extraction_is_whole_word():
    found = extract_skills("Used Python, C++ and sklearn. Wrote NoSQL and MySQL queries.")
    assert {"Python", "C++", "Scikit-learn", "MySQL"} <= found
    assert "SQL" not in found and "Java" not in found


# ---------- ATS rules ----------
def test_good_resume_has_no_high_issues(good_text):
    report = run_ats_check(parse_text(good_text))
    assert report.status in {"pass", "warn"}
    assert not [i for i in report.issues if i.severity == "high"]


def test_bad_resume_fails(bad_text):
    report = run_ats_check(parse_text(bad_text))
    assert report.status == "fail"
    assert {"garbled_text", "missing_email", "missing_phone", "first_person", "weak_phrases"} <= ids(report)


def test_table_and_image_rules(good_text):
    r = parse_text(good_text, has_tables=True, has_images=True)
    assert {"tables", "images"} <= ids(run_ats_check(r))


def test_mixed_date_formats_and_length(good_text):
    r = parse_text(good_text + "\nJun 2024 to 06/2025", page_count=3)
    assert {"date_formats", "too_long"} <= ids(run_ats_check(r))


def test_odd_bullets():
    r = parse_text("Skills\n➤ Python\n➤ SQL\n" + "filler text " * 40)
    assert "odd_bullets" in ids(run_ats_check(r))


# ---------- pipeline, scoring, matching ----------
def test_good_resume_outscores_bad(good_text, bad_text, jobs):
    good, bad = analyze_text(good_text, jobs), analyze_text(bad_text, jobs)
    assert 0 <= bad.score.total < good.score.total <= 100
    s = good.score
    assert s.ats_format <= 25 and s.keyword_match <= 30 and s.content_quality <= 25 and s.completeness <= 20


def test_matcher_ranks_vision_job_first(good_text, jobs):
    res = analyze_text(good_text, jobs)
    assert len(res.matches) == 10
    assert res.matches[0].job.title == "Computer Vision Engineer"
    assert all(0 <= m.match_percent <= 100 for m in res.matches)
    assert "OpenCV" in res.matches[0].matched


def test_empty_inputs_are_safe(jobs):
    assert rank_jobs("", set(), jobs) == []
    assert rank_jobs("python", {"Python"}, []) == []


def test_jobs_csv_validation():
    with pytest.raises(ValueError):
        load_jobs(b"a,b\n1,2\n")


# ---------- generator ----------
def test_generator_never_adds_skills(good_text, jobs):
    res = analyze_text(good_text, jobs)
    job = next(m.job for m in res.matches if m.job.title == "Machine Learning Engineer")
    for target in (None, job):
        gen = build_resume(res.resume, res.demand, target)
        skills_line = next(s for s in gen.sections if s.title == "Skills").blocks[0][1]
        assert extract_skills(skills_line) <= res.resume_skills
        assert gen.skills_to_learn and not set(gen.skills_to_learn) & res.resume_skills


def test_export_roundtrip(good_text, jobs):
    res = analyze_text(good_text, jobs)
    gen = build_resume(res.resume, res.demand)
    docx_bytes, pdf_bytes = to_docx(gen), to_pdf(gen)
    assert docx_bytes[:2] == b"PK" and pdf_bytes[:4] == b"%PDF"
    for name, data in (("out.docx", docx_bytes), ("out.pdf", pdf_bytes)):
        again = analyze(name, data, jobs)
        assert again.resume.contact["email"] == "ravi.kumar@example.com"
        assert again.score.total > 0


# ---------- LLM guard ----------
def test_llm_guard_blocks_invented_numbers():
    assert no_new_facts("Built a model with 94% accuracy", "Built a model reaching 94% accuracy")
    assert not no_new_facts("Built a model", "Built a model with 99% accuracy")
