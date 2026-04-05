from __future__ import annotations

from app.analyzers.base import AnalyzerResult
from app.fusion.fusion import FusionScorer


def test_fusion_high_ai_score_leads_to_ai_verdict():
    scorer = FusionScorer()
    scores, _, _ = scorer.score(
        text=AnalyzerResult(score=0.95, confidence=0.8),
        image=AnalyzerResult(score=0.8, confidence=0.7),
        video=AnalyzerResult(score=0.6, confidence=0.7),
        audio=AnalyzerResult(score=0.4, confidence=0.6),
        metadata_anomaly_score=0.1,
        qdrant_signal=0.2,
        cross_modal_consistency=0.9,
    )

    assert scores.ai_generated_score >= 0.7
    assert scores.verdict.value in {"likely_ai_generated", "likely_manipulated"}


def test_fusion_image_only_uses_image_confidence_and_mode():
    scorer = FusionScorer()
    scores, _, explanation = scorer.score(
        text=AnalyzerResult(score=0.0, confidence=0.0),
        image=AnalyzerResult(score=0.74, confidence=0.81),
        video=AnalyzerResult(score=0.0, confidence=0.0),
        audio=AnalyzerResult(score=0.0, confidence=0.0),
        metadata_anomaly_score=0.0,
        qdrant_signal=0.0,
        cross_modal_consistency=0.0,
    )

    assert abs(scores.confidence - 0.81) < 1e-9
    assert abs(scores.ai_generated_score - 0.74) < 1e-9
    assert "mode=image-only" in explanation
    assert scores.verdict.value == "likely_ai_generated"
