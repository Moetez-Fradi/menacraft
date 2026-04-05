from __future__ import annotations

import re
from collections import Counter


_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def clean_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text or "").strip()
    return collapsed


def lexical_variety(text: str) -> float:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def repetition_ratio(text: str) -> float:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if not words:
        return 0.0
    counts = Counter(words)
    repeated = sum(c for c in counts.values() if c > 1)
    return repeated / len(words)


def sentence_lengths(text: str) -> list[int]:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    return [len(_WORD_RE.findall(s)) for s in sentences]


def punctuation_density(text: str) -> float:
    if not text:
        return 0.0
    punct = sum(1 for ch in text if ch in ",.!?;:-")
    return punct / max(len(text), 1)
