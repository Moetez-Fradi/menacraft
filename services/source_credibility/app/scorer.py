"""
Score aggregation and risk-level mapping.

Scoring logic:
  - Base score = 1.0
  - Deductions per account signal:       -WEIGHT_ACCOUNT_SIGNAL  (default -0.2)
  - Deductions per suspicious domain:    -WEIGHT_SUSPICIOUS_DOMAIN (default -0.3)
  - Deduction for writing inconsistency: -WEIGHT_WRITING_STYLE   (default -0.2)
  - Final score clamped to [0, 1]

Risk mapping:
  score >= 0.75 → LOW
  0.40 <= score < 0.75 → MEDIUM
  score < 0.40 → HIGH
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from app.analyzers.account import AccountResult
from app.analyzers.links import LinksResult
from app.analyzers.writing_style import WritingStyleResult
from app.config import (
    WEIGHT_ACCOUNT_SIGNAL,
    WEIGHT_SUSPICIOUS_DOMAIN,
    WEIGHT_WRITING_STYLE,
)

logger = logging.getLogger(__name__)


class ScoreResult(NamedTuple):
    score: float
    risk_level: str  # LOW | MEDIUM | HIGH


def _map_risk(score: float) -> str:
    if score >= 0.75:
        return "LOW"
    if score >= 0.40:
        return "MEDIUM"
    return "HIGH"


def compute_score(
    account: AccountResult,
    links: LinksResult,
    writing: WritingStyleResult,
) -> ScoreResult:
    """Aggregate partial results into a final credibility score."""

    score = 1.0

    # Account heuristics — each flag deducts WEIGHT_ACCOUNT_SIGNAL
    account_deduction = account.penalty * WEIGHT_ACCOUNT_SIGNAL
    score -= account_deduction
    if account_deduction > 0:
        logger.debug(
            "Account deduction: -%.2f (%d signals)", account_deduction, int(account.penalty)
        )

    # Domain suspicion — each suspicious domain deducts WEIGHT_SUSPICIOUS_DOMAIN
    domain_deduction = links.penalty * WEIGHT_SUSPICIOUS_DOMAIN
    score -= domain_deduction
    if domain_deduction > 0:
        logger.debug(
            "Domain deduction: -%.2f (%d domains)", domain_deduction, int(links.penalty)
        )

    # Writing style
    if writing.inconsistent:
        score -= WEIGHT_WRITING_STYLE
        logger.debug("Writing style deduction: -%.2f", WEIGHT_WRITING_STYLE)

    # Clamp
    score = max(0.0, min(1.0, score))
    risk = _map_risk(score)

    logger.info("Final score: %.2f → risk: %s", score, risk)
    return ScoreResult(score=round(score, 4), risk_level=risk)
