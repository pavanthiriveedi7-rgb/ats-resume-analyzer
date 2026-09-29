"""Shared vocabularies and regular expressions."""
from __future__ import annotations

import re

ACTION_VERBS = frozenset("""
accelerated achieved administered analyzed applied architected assembled automated benchmarked built
collaborated configured contributed created debugged delivered deployed designed detected developed
documented drove engineered enhanced established evaluated executed extracted fine-tuned generated
implemented improved increased initiated integrated investigated launched led maintained managed
mentored migrated modeled monitored optimized orchestrated organized owned presented programmed
prototyped published reduced refactored researched resolved scaled secured simplified spearheaded
streamlined supported tested trained transformed tuned unified upgraded validated visualized wrote
""".split())

WEAK_PHRASES = (
    "responsible for", "worked on", "helped with", "helped to", "duties included",
    "in charge of", "tasked with", "involved in", "assisted in",
)
WEAK_RE = re.compile(r"\b(?:" + "|".join(map(re.escape, WEAK_PHRASES)) + r")\b", re.I)
FIRST_PERSON_RE = re.compile(r"\b(?:I|[Mm]y|[Mm]e|[Mm]yself)\b")
METRIC_RE = re.compile(r"(?<![A-Za-z0-9.])\d+(?:[.,]\d+)?")
BULLET_RE = re.compile(r"^\s*(?:[•●▪◦■□▶►➤➢✓✔❖★☆·]\s*|[*\-–—]\s+)(?=\S)")
UNUSUAL_BULLETS = frozenset("■□▶►➤➢✓✔❖★☆●◦▪")
