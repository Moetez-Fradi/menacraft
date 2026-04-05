from __future__ import annotations

from app.analyzers.base import AnalyzerResult
from app.shared.constants import Verdict
from app.shared.schemas import EvidenceItem, ScoreBundle
from app.shared.scoring import clamp01, weighted_avg


class FusionScorer:
    def score(
        self,
        text: AnalyzerResult,
        image: AnalyzerResult,
        video: AnalyzerResult,
        audio: AnalyzerResult,
        metadata_anomaly_score: float = 0.0,
        qdrant_signal: float = 0.0,
        cross_modal_consistency: float = 0.0,
    ) -> tuple[ScoreBundle, list[EvidenceItem], str]:
        has_text = text.confidence > 0.0
        has_image = image.confidence > 0.0
        has_video = video.confidence > 0.0
        has_audio = audio.confidence > 0.0

        active_modalities = [
            modality
            for modality, active in [
                ("text", has_text),
                ("image", has_image),
                ("video", has_video),
                ("audio", has_audio),
            ]
            if active
        ]
        mode = "multi-modal"
        if len(active_modalities) == 1:
            mode = f"{active_modalities[0]}-only"

        if mode == "text-only":
            ai_generated = clamp01(text.score)
        elif mode == "image-only":
            ai_generated = clamp01(image.score)
        elif mode == "video-only":
            ai_generated = clamp01(video.score)
        elif mode == "audio-only":
            ai_generated = clamp01(audio.score)
        else:
            ai_generated = clamp01(
                weighted_avg(
                    [
                        (text.score, 0.35),
                        (image.score, 0.25),
                        (video.score, 0.20),
                        (audio.score, 0.10),
                        (qdrant_signal, 0.05),
                        (metadata_anomaly_score, 0.05),
                    ]
                )
            )

        manipulation = clamp01(
            weighted_avg(
                [
                    (image.score, 0.40),
                    (video.score, 0.30),
                    (metadata_anomaly_score, 0.15),
                    (1 - cross_modal_consistency, 0.15),
                ]
            )
        )
        authenticity = clamp01(1.0 - (0.6 * ai_generated + 0.4 * manipulation))
        confidence = clamp01(
            weighted_avg(
                [
                    (text.confidence, 0.30),
                    (image.confidence, 0.25),
                    (video.confidence, 0.20),
                    (audio.confidence, 0.10),
                    (0.5 + 0.5 * cross_modal_consistency, 0.15),
                ]
            )
        )

        if mode == "text-only":
            confidence = clamp01(text.confidence)
        elif mode == "image-only":
            confidence = clamp01(image.confidence)
        elif mode == "video-only":
            confidence = clamp01(video.confidence)
        elif mode == "audio-only":
            confidence = clamp01(audio.confidence)

        if mode == "image-only":
            if confidence < 0.5:
                verdict = Verdict.UNCERTAIN
            elif ai_generated >= 0.58:
                verdict = Verdict.LIKELY_AI_GENERATED
            elif manipulation >= 0.6:
                verdict = Verdict.LIKELY_MANIPULATED
            elif authenticity >= 0.62:
                verdict = Verdict.LIKELY_AUTHENTIC
            else:
                verdict = Verdict.UNCERTAIN
        else:
            if confidence < 0.45:
                verdict = Verdict.UNCERTAIN
            elif ai_generated >= 0.7:
                verdict = Verdict.LIKELY_AI_GENERATED
            elif manipulation >= 0.65:
                verdict = Verdict.LIKELY_MANIPULATED
            elif authenticity >= 0.65:
                verdict = Verdict.LIKELY_AUTHENTIC
            else:
                verdict = Verdict.UNCERTAIN

        evidence = [*text.evidence, *image.evidence, *video.evidence, *audio.evidence]
        explanation = (
            f"Fusion combines text={text.score:.2f}, image={image.score:.2f}, "
            f"video={video.score:.2f}, audio={audio.score:.2f}, "
            f"qdrant={qdrant_signal:.2f}, mode={mode}."
        )
        if mode == "text-only":
            llm_explanation = str(text.debug.get("llm_explanation", "")).strip()
            features = text.debug.get("features", {})
            if isinstance(features, dict):
                rep = float(features.get("repetition", 0.0))
                lex = float(features.get("lexical_variety", 0.0))
                sent_var = float(features.get("sentence_variance", 0.0))
                explanation += (
                    f" Text diagnostics: repetition={rep:.2f}, lexical_variety={lex:.2f}, "
                    f"sentence_variance={sent_var:.2f}."
                )
            if llm_explanation:
                explanation += f" LLM rationale: {llm_explanation}"
        if mode == "image-only" and image.evidence:
            explanation += f" Top image evidence: {image.evidence[0].reason}"

        return (
            ScoreBundle(
                authenticity_score=authenticity,
                manipulation_score=manipulation,
                ai_generated_score=ai_generated,
                confidence=confidence,
                verdict=verdict,
            ),
            evidence,
            explanation,
        )
