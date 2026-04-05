"""
Pydantic models for request / response schemas.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ── Request models ──────────────────────────────────────────────────────────

class AuthorInfo(BaseModel):
    """Metadata about the content author / account."""

    username: str = Field(..., description="Account handle or display name")
    account_age_days: int = Field(
        ..., ge=0, description="How many days the account has existed"
    )
    followers: int = Field(..., ge=0)
    following: int = Field(..., ge=0)
    posts_count: int = Field(..., ge=0)


class ContentMetadata(BaseModel):
    """Contextual metadata about the piece of content."""

    timestamp: Optional[str] = Field(
        None, description="ISO-8601 timestamp of publication"
    )
    platform: Optional[str] = Field(
        None,
        description="Origin platform (twitter, instagram, tiktok, web, …)",
    )


class CredibilityRequest(BaseModel):
    """Inbound payload for the /analyze endpoint."""

    text: Optional[str] = Field(None, description="Post body or article text")
    author: AuthorInfo
    content_metadata: Optional[ContentMetadata] = None
    links: list[str] = Field(default_factory=list)


# ── Response models ─────────────────────────────────────────────────────────

class CredibilityResponse(BaseModel):
    """Structured credibility analysis result."""

    credibility_score: float = Field(
        ..., ge=0.0, le=1.0, description="0 = not credible, 1 = fully credible"
    )
    risk_level: str = Field(
        ..., description="LOW | MEDIUM | HIGH"
    )
    flags: list[str] = Field(
        default_factory=list,
        description="List of triggered warning flags",
    )
    explanation: str = Field(
        ..., description="Human-readable summary of the assessment"
    )
