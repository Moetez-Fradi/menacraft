from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.shared.constants import ContextVerdict
from app.shared.schemas import RetrievalResult


class ContextAnalyzeRequest(BaseModel):
    case_id: str
    claim_text: str
    platform_metadata: dict[str, Any] = Field(default_factory=dict)
    reference_hints: dict[str, Any] = Field(default_factory=dict)
    artifacts_override: dict[str, Any] | None = None


class ContextSignal(BaseModel):
    type: str
    severity: str
    reason: str


class ContextAnalyzeResponse(BaseModel):
    case_id: str
    consistency_score: float
    confidence: float
    verdict: ContextVerdict
    signals: list[ContextSignal] = Field(default_factory=list)
    suspicious_parts: list[dict[str, str]] = Field(default_factory=list)
    references: list[RetrievalResult] = Field(default_factory=list)
    explanation: str
    debug: dict[str, Any] = Field(default_factory=dict)
