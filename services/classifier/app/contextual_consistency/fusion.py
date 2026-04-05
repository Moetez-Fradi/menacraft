from __future__ import annotations

from app.contextual_consistency.schemas import ContextSignal
from app.shared.constants import ContextVerdict


class ContextFusion:
    def fuse(
        self,
        rules: list[dict[str, str]],
        entailment: dict[str, float | str],
        llm: dict[str, object],
        references_top_score: float,
    ) -> tuple[float, float, ContextVerdict, list[ContextSignal], str]:
        rule_penalty = min(0.7, 0.18 * len(rules))
        entailment_label = str(entailment.get("label", "neutral"))
        entailment_score = float(entailment.get("score", 0.5))

        llm_score = float(llm.get("consistency_score", 0.5)) if "error" not in llm else 0.5
        llm_conf = float(llm.get("confidence", 0.0))

        contradiction_penalty = 0.25 if entailment_label == "contradiction" else 0.0
        reuse_penalty = 0.20 if references_top_score > 0.9 else 0.0

        consistency = max(0.0, min(1.0, 0.45 * llm_score + 0.35 * entailment_score + 0.20 * (1 - rule_penalty) - contradiction_penalty - reuse_penalty))
        confidence = max(0.0, min(1.0, 0.30 + 0.4 * llm_conf + 0.3 * (1 - min(rule_penalty, 1.0))))

        if confidence < 0.45:
            verdict = ContextVerdict.UNCERTAIN
        elif consistency < 0.35:
            verdict = ContextVerdict.LIKELY_MISCONTEXTED
        elif consistency >= 0.65:
            verdict = ContextVerdict.CONSISTENT
        else:
            verdict = ContextVerdict.UNCERTAIN

        signals = [
            ContextSignal(type="rule", severity=r.get("severity", "low"), reason=r.get("reason", ""))
            for r in rules
        ]
        if references_top_score > 0.9:
            signals.append(
                ContextSignal(
                    type="reference_reuse",
                    severity="high",
                    reason="A near-duplicate reference suggests the content was previously used in another context.",
                )
            )

        explanation = str(llm.get("short_explanation", "Context fusion completed using rules, retrieval, entailment, and LLM."))
        return consistency, confidence, verdict, signals, explanation
