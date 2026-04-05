from __future__ import annotations

from app.analyzers.text_analyzer import TextAnalyzer
from app.analyzers.base import AnalyzerResult
from app.fusion.fusion import FusionScorer


class _StubLLM:
    def is_configured(self) -> bool:
        return True

    def chat_json(self, *args, **kwargs):
        return {
            "ai_probability": 0.80,
            "confidence": 0.9,
            "explanation": "Structured instructional tone and distributional regularity are typical of generated text.",
            "suspicious_spans": [],
        }


def test_text_analyzer_emits_evidence_at_threshold_score():
    analyzer = TextAnalyzer(llm_client=_StubLLM())
    result = analyzer.analyze(
        "Artificial intelligence systems can optimize outputs through iterative updates and probabilistic inference."
    )

    assert result.score >= 0.8
    assert result.evidence
    assert any(item.type in {"text_span", "text_signal"} for item in result.evidence)


def test_fusion_text_only_includes_llm_and_feature_explanation():
    scorer = FusionScorer()
    text = AnalyzerResult(
        score=0.8,
        confidence=0.9,
        debug={
            "llm_explanation": "Model sees generated style patterns.",
            "features": {
                "repetition": 0.22,
                "lexical_variety": 0.81,
                "sentence_variance": 19.4,
            },
        },
    )
    scores, _, explanation = scorer.score(
        text=text,
        image=AnalyzerResult(score=0.0, confidence=0.0),
        video=AnalyzerResult(score=0.0, confidence=0.0),
        audio=AnalyzerResult(score=0.0, confidence=0.0),
    )

    assert scores.verdict.value == "likely_ai_generated"
    assert "mode=text-only" in explanation
    assert "Text diagnostics:" in explanation
    assert "LLM rationale:" in explanation