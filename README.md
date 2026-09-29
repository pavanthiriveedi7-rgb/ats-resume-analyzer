# Resume Analyzer Lite

An offline Streamlit app that checks a resume for ATS-friendliness, scores it out of 100, matches it against 10 job descriptions, lists mistakes with fixes, and builds an improved resume (DOCX and PDF). An LLM is optional and only used to polish bullet rewrites.

## Run

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
python -m pytest                                    # 15 tests
```

Optional AI polish: copy `.env.example` to `.env` and set `LLM_API_KEY` (and `LLM_PROVIDER=anthropic|openai`).

## Architecture

```
app.py                Streamlit entry point (wiring only)
ui/components.py      Rendering helpers: gauge, cards, pills
core/
  models.py           Dataclasses: Issue, ParsedResume, Job, ScoreBreakdown, JobMatch
  parser.py           PDF / DOCX / TXT -> sections, contact, bullets
  skills.py           Skill taxonomy (data/skills.txt) + whole-word extraction
  ats.py              9 rule functions -> ATSReport (pass / warn / fail)
  scorer.py           Four sub-scores -> total out of 100
  matcher.py          TF-IDF cosine + skill overlap -> ranked jobs
  suggestions.py      ATS issues + content analysis -> prioritised fixes
  generator.py        Master / tailored resume + DOCX and PDF export
  llm.py              Optional rewrite layer with a no-invented-numbers guard
  pipeline.py         parse -> ats -> match -> score -> suggestions
data/jobs.csv         10 SAMPLE job descriptions (replace with real ones)
data/skills.txt       Skill taxonomy: Name|alias|alias
```

## Scoring (100)

| Part | Max | How |
|---|---|---|
| ATS format | 25 | 25 minus 6 per high, 3 per medium, 1 per low issue |
| Keyword match | 30 | Share of the 25 most demanded skills (across the job set) found in the resume |
| Content quality | 25 | Per bullet: 0.5 for an action verb, 0.5 for a number; minus weak-phrase penalty |
| Completeness | 20 | Sections, contact details, links, projects or certifications |

Job match % = 70% TF-IDF similarity (rescaled by a 0.35 ceiling) + 30% skill overlap, plus 5 if the target role matches the title.

## Honesty rules

The generator never adds a skill, employer, date, or number that isn't already in the resume. Missing skills go into a separate "Skills to learn" list. The AI layer discards any rewrite that introduces a new number.

## Limits

- The 10 jobs are sample data from a local CSV, not live listings. Upload your own CSV in the sidebar (columns: id, title, company, location, description).
- Scanned or image-only PDFs can't be read (there is no OCR); the app flags them as an ATS failure.
- Skill matching depends on `data/skills.txt`. Add skills there for other domains.
