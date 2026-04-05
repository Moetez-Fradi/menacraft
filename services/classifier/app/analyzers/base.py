from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.shared.schemas import EvidenceItem


@dataclass
class AnalyzerResult:
    score: float
    confidence: float
    evidence: list[EvidenceItem] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)


class BaseAnalyzer:
    name = "base"

    def analyze(self, *args: Any, **kwargs: Any) -> AnalyzerResult:
        raise NotImplementedError
