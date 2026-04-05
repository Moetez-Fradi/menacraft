from __future__ import annotations

from app.contextual_consistency.fusion import ContextFusion


def test_context_fusion_flags_miscontexted_on_strong_reuse_and_rules():
    fusion = ContextFusion()
    consistency, confidence, verdict, signals, _ = fusion.fuse(
        rules=[{"severity": "high", "reason": "breaking_old"}],
        entailment={"label": "contradiction", "score": 0.2},
        llm={"consistency_score": 0.15, "confidence": 0.9, "short_explanation": "Mismatch"},
        references_top_score=0.95,
    )

    assert consistency < 0.4
    assert verdict.value == "likely_miscontexted"
    assert confidence >= 0.45
    assert len(signals) >= 1
