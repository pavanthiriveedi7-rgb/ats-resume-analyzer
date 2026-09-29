"""Resume Analyzer Lite - Streamlit entry point. Run: streamlit run app.py"""
from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from core.generator import build_resume, to_docx, to_pdf
from core.llm import LLMClient, LLMError
from core.matcher import load_jobs
from core.parser import ResumeParseError
from core.pipeline import analyze
from ui import components as ui

load_dotenv()
st.set_page_config(page_title="Resume Analyzer Lite", page_icon="📄", layout="wide")
st.title("Resume Analyzer Lite")
st.caption("ATS check, score, job matching, and an improved resume. Runs offline; AI polish is optional.")


@st.cache_data(show_spinner=False)
def cached_jobs(csv_bytes: bytes | None):
    return load_jobs(csv_bytes)


with st.sidebar:
    st.header("Your resume")
    resume_file = st.file_uploader("Upload resume", type=["pdf", "docx", "txt"], help="Max 5 MB")
    jobs_file = st.file_uploader("Custom jobs CSV (optional)", type=["csv"],
                                 help="Columns: id, title, company, location, description")
    role = st.text_input("Target role (optional)", placeholder="Python developer")
    run = st.button("Analyze resume", type="primary", use_container_width=True)

if run:
    if resume_file is None:
        st.sidebar.error("Upload a resume first.")
    else:
        try:
            jobs = cached_jobs(jobs_file.getvalue() if jobs_file else None)
            with st.spinner("Analyzing your resume..."):
                st.session_state.result = analyze(resume_file.name, resume_file.getvalue(), jobs, role)
            st.session_state.tailor_id = None
        except (ResumeParseError, ValueError) as exc:
            st.session_state.pop("result", None)
            st.error(str(exc))

res = st.session_state.get("result")
if res is None:
    st.info("Upload a resume in the sidebar and press Analyze resume.")
    st.stop()

st.subheader("1. Score and ATS check")
ui.score_section(res.score, res.ats)

st.subheader("2. Mistakes and suggestions")
ui.issues_section(res.suggestions)
llm = LLMClient()
weak = [b for b in res.resume.bullets][:6]
if llm.available and weak and st.button("Improve my bullets with AI"):
    try:
        with st.spinner("Rewriting..."):
            for old, new in llm.rewrite_bullets(weak).items():
                st.markdown(f"~~{old}~~  \n**{new}**")
    except LLMError as exc:
        st.error(str(exc))

st.subheader("3. Top job matches")
if res.matches:
    picked = ui.job_cards(res.matches, st.session_state.get("tailor_id"))
    if picked:
        st.session_state.tailor_id = picked
        st.rerun()
else:
    st.warning("No jobs to match against. Check your jobs CSV.")

st.subheader("4. Resume studio")
job = next((m.job for m in res.matches if m.job.id == st.session_state.get("tailor_id")), None)
gen = build_resume(res.resume, res.demand, job)
st.caption(f"Building: {'tailored for ' + job.title if job else 'master resume for all matched jobs'}")
if job and st.button("Back to master resume"):
    st.session_state.tailor_id = None
    st.rerun()

before, after = st.columns(2)
with before:
    st.markdown("**Before**")
    st.text_area("Original text", res.resume.raw_text, height=380, label_visibility="collapsed", disabled=True)
with after:
    st.markdown("**After**")
    preview = [f"**{gen.name}**  \n{gen.contact_line}"]
    for sec in gen.sections:
        preview.append(f"**{sec.title.upper()}**")
        preview += [("- " if k == "b" else "") + t for k, t in sec.blocks]
    with st.container(height=380, border=True):
        st.markdown("\n\n".join(preview))

with st.expander("What changed"):
    st.markdown("\n".join(f"- {line}" for line in gen.change_log))
if gen.skills_to_learn:
    st.info("Skills to learn (not added to your resume): " + ", ".join(gen.skills_to_learn))

d1, d2 = st.columns(2)
d1.download_button("Download DOCX", to_docx(gen), "resume.docx",
                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
d2.download_button("Download PDF", to_pdf(gen), "resume.pdf", "application/pdf", use_container_width=True)
