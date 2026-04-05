from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.shared.constants import ContextVerdict, Verdict


class LLMMessage(BaseModel):
    role: str
    content: str
    images: list[str] | None = None


class EvidenceItem(BaseModel):
    type: str
    reason: str
    confidence: float = Field(ge=0, le=1)
    artifact_id: str | None = None
    span: str | None = None
    timestamp_ms: int | None = None
    region: dict[str, Any] | None = None
    debug: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    artifact_id: str
    similarity: float
    label: str | None = None
    modality: str
    explanation: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ScoreBundle(BaseModel):
    authenticity_score: float = Field(ge=0, le=1)
    manipulation_score: float = Field(ge=0, le=1)
    ai_generated_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    verdict: Verdict


class ContextScoreBundle(BaseModel):
    consistency_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    verdict: ContextVerdict


class MediaArtifact(BaseModel):
    artifact_id: str
    modality: str
    path: str
    hash_sha256: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimObject(BaseModel):
    original_text: str
    entities: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class CaseInput(BaseModel):
    session_id: str | None = None
    text: str | None = None
    clean_text: str | None = None
    image_base64: str | None = None
    clean_image_base64: str | None = None
    media_urls: list[str] = Field(default_factory=list)
    content_type: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedArtifacts(BaseModel):
    case_id: str
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    normalized_text: str = ""
    image_artifacts: list[MediaArtifact] = Field(default_factory=list)
    video_frame_artifacts: list[MediaArtifact] = Field(default_factory=list)
    audio_artifacts: list[MediaArtifact] = Field(default_factory=list)
    transcripts: list[str] = Field(default_factory=list)
    ocr_text: list[str] = Field(default_factory=list)
    technical_metadata: dict[str, Any] = Field(default_factory=dict)
    hashes: dict[str, str] = Field(default_factory=dict)
    paths: dict[str, str] = Field(default_factory=dict)


class SuspiciousSpan(BaseModel):
    text: str
    reason: str


class SuspiciousTimestamp(BaseModel):
    timestamp_ms: int
    reason: str
    frame_artifact_id: str | None = None


class AnalysisReport(BaseModel):
    case_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    scores: ScoreBundle | None = None
    context_scores: ContextScoreBundle | None = None
    verdict: str | None = None
    suspicious_parts: list[SuspiciousSpan] = Field(default_factory=list)
    suspicious_timestamps: list[SuspiciousTimestamp] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    references: list[RetrievalResult] = Field(default_factory=list)
    explanation: str = ""
    debug: dict[str, Any] = Field(default_factory=dict)
    model_versions: dict[str, str] = Field(default_factory=dict)


class JobStatus(str, Enum):
    ACCEPTED = "accepted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyzeAcceptedResponse(BaseModel):
    case_id: str
    job_status: JobStatus
    accepted_at: datetime
    input_summary: dict[str, Any]


class FeedbackRequest(BaseModel):
    case_id: str
    label: str
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LegacyAnalyzeRequest(BaseModel):
    session_id: str
    clean_text: str = ""
    clean_image_base64: str | None = None
    content_type: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)
