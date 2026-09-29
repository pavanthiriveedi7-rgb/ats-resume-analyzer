"""Streamlit rendering helpers. No business logic lives here."""
from __future__ import annotations

from html import escape

import plotly.graph_objects as go
import streamlit as st

from core.ats import ATSReport
from core.models import Issue, JobMatch, ScoreBreakdown

_BADGE = {"pass": ("#1a7f37", "ATS friendly"), "warn": ("#b7791f", "Needs fixes"), "fail": ("#c62828", "Not ATS friendly")}
_SEV = {"high": "#c62828", "medium": "#b7791f", "low": "#1a7f37"}


def pill(text: str, color: str) -> str:
    return (f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 10px;border-radius:8px;'
            f'font-size:12px;border:1px solid {color};color:{color}">{escape(text)}</span>')


def gauge(score: ScoreBreakdown) -> None:
    color = "#1a7f37" if score.total >= 75 else "#b7791f" if score.total >= 50 else "#c62828"
    fig = go.Figure(go.Indicator(mode="gauge+number", value=score.total, gauge={
        "axis": {"range": [0, 100]}, "bar": {"color": color, "thickness": 0.3}}))
    fig.update_layout(height=230, margin=dict(l=20, r=20, t=20, b=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)


def score_section(score: ScoreBreakdown, ats: ATSReport) -> None:
    left, right = st.columns([1, 2])
    with left:
        gauge(score)
        color, label = _BADGE[ats.status]
        st.markdown(f'<div style="text-align:center">{pill(label, color)}</div>', unsafe_allow_html=True)
    with right:
        cols = st.columns(2)
        cols[0].metric("ATS format", f"{score.ats_format:.0f} / 25")
        cols[1].metric("Keyword match", f"{score.keyword_match:.0f} / 30")
        cols[0].metric("Content quality", f"{score.content_quality:.0f} / 25")
        cols[1].metric("Completeness", f"{score.completeness:.0f} / 20")
        st.caption(score.explanation)


def issues_section(issues: list[Issue]) -> None:
    if not issues:
        st.success("No issues found.")
    for i, issue in enumerate(issues):
        with st.expander(f"{issue.severity.upper()} | {issue.section} | {issue.message}", expanded=(i < 2)):
            st.markdown(f"**Fix:** {issue.fix}")
            if issue.example:
                st.code(issue.example, language="text")


def job_cards(matches: list[JobMatch], selected: str | None) -> str | None:
    """Render job cards; return the id of a job whose 'Tailor' button was pressed."""
    picked = None
    for row in range(0, len(matches), 2):
        cols = st.columns(2)
        for col, m in zip(cols, matches[row:row + 2]):
            with col.container(border=True):
                st.markdown(f"**{m.job.title}** · {m.job.company}  \n{m.job.location}")
                st.progress(m.match_percent / 100, text=f"{m.match_percent}% match")
                html = "".join(pill(s, "#1a7f37") for s in m.matched) + "".join(pill(s, "#c62828") for s in m.missing)
                st.markdown(html or "No skills detected in this JD.", unsafe_allow_html=True)
                label = "Selected" if selected == m.job.id else "Tailor resume"
                if st.button(label, key=f"tailor_{m.job.id}", use_container_width=True):
                    picked = m.job.id
    st.caption("Green = skill you have. Red = skill this job asks for that your resume lacks.")
    return picked
