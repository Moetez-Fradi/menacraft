from __future__ import annotations

from app.analyzers.base import AnalyzerResult, BaseAnalyzer
from app.shared.schemas import EvidenceItem


class AudioAnalyzer(BaseAnalyzer):
    name = "audio"

    def analyze(self, audio_paths: list[str], transcript: str | None = None) -> AnalyzerResult:
        if not audio_paths and not transcript:
            return AnalyzerResult(score=0.0, confidence=0.0, debug={"reason": "no_audio"})

        if not transcript:
            return AnalyzerResult(
                score=0.0,
                confidence=0.1,
                evidence=[],
                debug={"ai_feature_error": "transcription_not_available"},
            )

        suspicious = "robotic" in transcript.lower() or "synthetic voice" in transcript.lower()
        score = 0.65 if suspicious else 0.25
        evidence = []
        if suspicious:
            evidence.append(
                EvidenceItem(
                    type="audio_interval",
                    reason="Transcript indicates potentially synthetic voice",
                    confidence=0.62,
                    timestamp_ms=0,
                )
            )

        return AnalyzerResult(score=score, confidence=0.55, evidence=evidence, debug={"transcript_len": len(transcript)})
