"""Optional LLM layer. The app works fully without it; this only polishes bullet rewrites."""
from __future__ import annotations

import json
import os
import re

import requests

from .lexicon import METRIC_RE

SYSTEM = ("You improve resume bullet points. Rewrite each bullet to start with a strong action verb and be concise. "
          "Use ONLY facts present in the original bullet. Never add numbers, tools, employers, or results that are not "
          "already there. Reply with only a JSON object mapping each original bullet to its rewrite.")
DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o-mini"}


class LLMError(RuntimeError):
    """Raised with a user-friendly message when the LLM call fails."""


def _numbers(text: str) -> set[str]:
    return set(METRIC_RE.findall(text))


def no_new_facts(original: str, rewrite: str) -> bool:
    """Reject rewrites that introduce numbers not present in the original bullet."""
    return _numbers(rewrite) <= _numbers(original)


class LLMClient:
    def __init__(self) -> None:
        self.key = os.getenv("LLM_API_KEY", "").strip()
        self.provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
        self.model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS.get(self.provider, "")

    @property
    def available(self) -> bool:
        return bool(self.key) and self.provider in DEFAULT_MODELS

    def _complete(self, user: str) -> str:
        if self.provider == "anthropic":
            resp = requests.post(
                "https://api.anthropic.com/v1/messages", timeout=40,
                headers={"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": self.model, "max_tokens": 1500, "system": SYSTEM,
                      "messages": [{"role": "user", "content": user}]})
            resp.raise_for_status()
            return "".join(b.get("text", "") for b in resp.json()["content"])
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions", timeout=40,
            headers={"Authorization": f"Bearer {self.key}"},
            json={"model": self.model, "messages": [{"role": "system", "content": SYSTEM},
                                                    {"role": "user", "content": user}]})
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def rewrite_bullets(self, bullets: list[str]) -> dict[str, str]:
        if not self.available:
            raise LLMError("No LLM key is set. Add LLM_API_KEY to your .env file.")
        try:
            raw = self._complete(json.dumps(bullets, ensure_ascii=False))
            data = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip())
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise LLMError("The AI rewrite failed. Check your key and try again.") from exc
        return {o: r for o, r in data.items() if o in bullets and isinstance(r, str) and no_new_facts(o, r)}
