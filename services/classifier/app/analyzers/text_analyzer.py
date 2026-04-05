from __future__ import annotations

import logging
import re
from statistics import variance

from app.analyzers.base import AnalyzerResult, BaseAnalyzer
from app.clients.ollama_client import OllamaLLMClient
from app.shared.schemas import EvidenceItem, LLMMessage, SuspiciousSpan
from app.shared.text_utils import lexical_variety, punctuation_density, repetition_ratio, sentence_lengths

logger = logging.getLogger(__name__)


class TextAnalyzer(BaseAnalyzer):
    name = "text"

    def __init__(self, llm_client: OllamaLLMClient) -> None:
        self.llm_client = llm_client

    def analyze(self, text: str) -> AnalyzerResult:
        if not text.strip():
            return AnalyzerResult(score=0.0, confidence=0.0, debug={"reason": "no_text"})

        features = self._feature_score(text)
        style_flags = self._style_flags(text)
        llm_score = None
        llm_confidence = 0.0
        llm_explanation = ""
        suspicious_spans: list[SuspiciousSpan] = []
        errors: list[str] = []
        evidence: list[EvidenceItem] = []

        if self.llm_client.is_configured():
            try:
                llm_payload = self.llm_client.chat_json(
                    [
                        LLMMessage(
                            role="system",
                            content=(
                                "You are a strict detector. Return JSON with keys: "
                                "ai_probability (0..1), confidence (0..1), explanation, suspicious_spans. "
                                "Treat excessive emoji usage and repeated em-dash separators (—) as potential "
                                "style signals, but never as sole proof. Use them only alongside broader linguistic evidence."
                            ),
                        ),
                        LLMMessage(
                            role="user",
                            content=(
                                f"Analyze text:\n{text[:4000]}\n\n"
                                f"Style diagnostics: emoji_count={style_flags['emoji_count']}, "
                                f"emoji_density={style_flags['emoji_density']:.4f}, "
                                f"em_dash_count={style_flags['em_dash_count']}, "
                                f"em_dash_density={style_flags['em_dash_density']:.4f}."
                            ),
                        ),
                    ]
                )
                llm_score = float(llm_payload.get("ai_probability", 0.0))
                llm_confidence = float(llm_payload.get("confidence", 0.0))
                explanation_raw = llm_payload.get("explanation", "")
                if isinstance(explanation_raw, str):
                    llm_explanation = explanation_raw.strip()
                elif isinstance(explanation_raw, list):
                    normalized_items = []
                    for item in explanation_raw:
                        if isinstance(item, dict):
                            snippet = str(item.get("text", "")).strip()
                            reason = str(item.get("reason", "")).strip() or "high AI probability"
                            if snippet:
                                suspicious_spans.append(SuspiciousSpan(text=snippet, reason=reason))
                                normalized_items.append(f"{snippet} ({reason})")
                        else:
                            normalized_items.append(str(item))
                    llm_explanation = "; ".join(normalized_items)
                else:
                    llm_explanation = str(explanation_raw).strip()

                spans_raw = llm_payload.get("suspicious_spans", []) or []
                if isinstance(spans_raw, list):
                    for raw in spans_raw:
                        if not isinstance(raw, dict):
                            continue
                        snippet = str(raw.get("text", "")).strip()
                        reason = str(raw.get("reason", "")).strip() or "high AI probability"
                        if snippet and not any(existing.text == snippet for existing in suspicious_spans):
                            suspicious_spans.append(SuspiciousSpan(text=snippet, reason=reason))
            except Exception as exc:
                errors.append(f"ollama_failed:{exc}")
        else:
            errors.append("ollama_not_configured")

        blended = 0.5
        confidence = 0.15
        if llm_score is not None:
            blended = llm_score
            confidence = llm_confidence
        else:
            evidence.append(
                EvidenceItem(
                    type="ai_feature_unavailable",
                    reason="Ollama text judge unavailable; result confidence reduced",
                    confidence=0.1,
                    span=None,
                )
            )

        if blended >= 0.75:
            if suspicious_spans:
                for span in suspicious_spans[:6]:
                    evidence.append(
                        EvidenceItem(
                            type="text_span",
                            reason=span.reason,
                            confidence=confidence,
                            span=span.text,
                        )
                    )
            else:
                for sentence in self._fallback_spans(text):
                    evidence.append(
                        EvidenceItem(
                            type="text_span",
                            reason="high AI probability with repetitive/statistical patterns",
                            confidence=confidence,
                            span=sentence,
                        )
                    )

                evidence.append(
                    EvidenceItem(
                        type="text_signal",
                        reason="LLM indicates likely AI-generated style in overall writing structure",
                        confidence=confidence,
                        span=None,
                        debug={
                            "llm_explanation": llm_explanation,
                            "feature_score": features.get("score", 0.0),
                                        "style_flags": style_flags,
                        },
                    )
                )

        return AnalyzerResult(
            score=max(0.0, min(1.0, blended)),
            confidence=max(0.0, min(1.0, confidence)),
            evidence=evidence,
            debug={
                "features": features,
                "errors": errors,
                "llm_used": llm_score is not None,
                "ai_feature_status": "ok" if llm_score is not None else "unavailable",
                "llm_ai_probability": llm_score,
                "llm_confidence": llm_confidence if llm_score is not None else None,
                "llm_explanation": llm_explanation if llm_score is not None else "",
                "style_flags": style_flags,
            },
        )

    def _feature_score(self, text: str) -> dict[str, float]:
        lengths = sentence_lengths(text)
        sent_var = variance(lengths) if len(lengths) >= 2 else 0.0
        rep = repetition_ratio(text)
        lex = lexical_variety(text)
        punct = punctuation_density(text)

        markers = len(re.findall(r"\b(furthermore|moreover|in conclusion|overall|therefore)\b", text.lower()))
        marker_score = min(markers / 6.0, 1.0)

        score = (
            0.30 * rep
            + 0.20 * (1.0 - min(lex, 1.0))
            + 0.20 * min(marker_score, 1.0)
            + 0.15 * (1.0 if sent_var < 15 else 0.0)
            + 0.15 * min(punct * 12, 1.0)
        )
        confidence = 0.35 + 0.65 * min(max(len(text) / 1200, 0.0), 1.0)

        return {
            "score": float(max(0.0, min(1.0, score))),
            "confidence": float(max(0.0, min(1.0, confidence))),
            "repetition": rep,
            "lexical_variety": lex,
            "sentence_variance": float(sent_var),
            "punctuation_density": punct,
            "marker_score": marker_score,
        }

    def _style_flags(self, text: str) -> dict[str, float]:
        emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF]", text))
        em_dash_count = text.count("—")
        text_len = max(1, len(text))
        return {
            "emoji_count": float(emoji_count),
            "emoji_density": float(emoji_count / text_len),
            "em_dash_count": float(em_dash_count),
            "em_dash_density": float(em_dash_count / text_len),
        }

    def _fallback_spans(self, text: str) -> list[str]:
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 25]
        return sentences[:3]
