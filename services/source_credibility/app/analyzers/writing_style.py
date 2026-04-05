"""
Writing-style consistency analysis.

Two modes:
  1. LLM-based (via OpenRouter) — preferred when OPENROUTER_API_KEY is set
  2. Heuristic fallback — regex-based spam / bot pattern detection

The function always returns quickly; if the LLM call fails, the
heuristic fallback is used transparently.
"""

from __future__ import annotations

import json
import logging
import re
from typing import NamedTuple

import httpx

from app.config import (
    LLM_ENABLED,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
)

logger = logging.getLogger(__name__)

# ── Heuristic patterns for bot / spam detection ─────────────────────────────

_SPAM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(click here|buy now|act fast|limited time|100% free)", re.I),
    re.compile(r"(earn \$|make money|bitcoin|crypto|nft)", re.I),
    re.compile(r"(!!!|\.{4,}|\?{3,})", re.I),
    re.compile(r"(dm me|link in bio|check my profile)", re.I),
    re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]{5,}"),  # emoji flood
]

# Caps-lock ratio threshold
_CAPS_RATIO_THRESHOLD = 0.6
_MIN_TEXT_LENGTH = 20  # skip analysis for very short texts


class WritingStyleResult(NamedTuple):
    inconsistent: bool
    method: str  # "llm" | "heuristic" | "skipped"
    detail: str


# ── Heuristic analyser ──────────────────────────────────────────────────────

def _heuristic_analysis(text: str) -> WritingStyleResult:
    """Fast, offline analysis using regex patterns and character stats."""

    if len(text.strip()) < _MIN_TEXT_LENGTH:
        return WritingStyleResult(
            inconsistent=False,
            method="skipped",
            detail="Text too short for meaningful analysis",
        )

    hits: list[str] = []

    # Spam patterns
    for pat in _SPAM_PATTERNS:
        if pat.search(text):
            hits.append(f"matched pattern: {pat.pattern[:40]}")

    # Caps-lock abuse
    alpha = [c for c in text if c.isalpha()]
    if alpha:
        caps_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
        if caps_ratio > _CAPS_RATIO_THRESHOLD:
            hits.append(f"excessive caps ({caps_ratio:.0%})")

    # Repetitive phrases (same 4+ word n-gram appears 3+ times)
    words = text.lower().split()
    if len(words) >= 4:
        ngrams: dict[str, int] = {}
        for i in range(len(words) - 3):
            ng = " ".join(words[i : i + 4])
            ngrams[ng] = ngrams.get(ng, 0) + 1
        for ng, cnt in ngrams.items():
            if cnt >= 3:
                hits.append(f"repetitive phrase ({cnt}×): '{ng}'")

    inconsistent = len(hits) > 0
    return WritingStyleResult(
        inconsistent=inconsistent,
        method="heuristic",
        detail="; ".join(hits) if hits else "No suspicious patterns detected",
    )


# ── LLM analyser ───────────────────────────────────────────────────────────

_LLM_SYSTEM_PROMPT = (
    "You are a writing-style analyst for a misinformation detection system. "
    "Analyze the following social media post or article text and determine "
    "whether the writing style appears legitimate or shows signs of being "
    "bot-generated, spam-like, or tonally inconsistent.\n\n"
    "Respond ONLY with valid JSON:\n"
    '{"inconsistent": true/false, "reason": "short explanation"}'
)


async def _llm_analysis(text: str) -> WritingStyleResult | None:
    """Call OpenRouter for writing-style analysis.  Returns None on failure."""

    if not OPENROUTER_API_KEY:
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                        {"role": "user", "content": text[:2000]},  # cap length
                    ],
                    "max_tokens": 150,
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            result = json.loads(content)
            return WritingStyleResult(
                inconsistent=bool(result.get("inconsistent", False)),
                method="llm",
                detail=result.get("reason", "LLM analysis complete"),
            )
    except Exception as exc:
        logger.warning("LLM analysis failed, falling back to heuristic: %s", exc)
        return None


# ── Public API ──────────────────────────────────────────────────────────────

async def analyze_writing_style(text: str | None) -> WritingStyleResult:
    """
    Analyse the writing style of the given text.

    - If text is None or empty, analysis is skipped.
    - If LLM is enabled and available, uses the LLM path.
    - Falls back to heuristics on LLM failure or when disabled.
    """

    if not text or len(text.strip()) < _MIN_TEXT_LENGTH:
        return WritingStyleResult(
            inconsistent=False,
            method="skipped",
            detail="No text provided or text too short",
        )

    # Try LLM first
    if LLM_ENABLED:
        llm_result = await _llm_analysis(text)
        if llm_result is not None:
            logger.info("Writing style analysed via LLM: %s", llm_result.detail)
            return llm_result

    # Fallback
    return _heuristic_analysis(text)
