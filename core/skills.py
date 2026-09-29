"""Skill taxonomy loading and whole-word skill extraction."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SKILLS = DATA_DIR / "skills.txt"


def _alias_pattern(alias: str) -> str:
    return re.escape(alias.strip()).replace("\\ ", r"\s+")


@lru_cache(maxsize=4)
def load_skills(path: str | None = None) -> dict[str, re.Pattern[str]]:
    """Return {display name: compiled pattern}. File format: `Name|alias|alias` per line."""
    file = Path(path) if path else DEFAULT_SKILLS
    skills: dict[str, re.Pattern[str]] = {}
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, *aliases = [p.strip() for p in line.split("|") if p.strip()]
        alts = sorted({name, *aliases}, key=len, reverse=True)
        body = "|".join(_alias_pattern(a) for a in alts)
        skills[name] = re.compile(rf"(?<![A-Za-z0-9_+#])(?:{body})(?![A-Za-z0-9_])", re.I)
    return skills


def extract_skills(text: str, skills: dict[str, re.Pattern[str]] | None = None) -> set[str]:
    """Skills from the taxonomy that appear in `text` (case-insensitive, whole word)."""
    skills = skills or load_skills()
    return {name for name, pat in skills.items() if pat.search(text)}
