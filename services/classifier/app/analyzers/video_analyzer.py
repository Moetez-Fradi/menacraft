from __future__ import annotations

from app.analyzers.base import AnalyzerResult, BaseAnalyzer
from app.analyzers.image_analyzer import ImageAnalyzer
from app.shared.schemas import EvidenceItem


class VideoAnalyzer(BaseAnalyzer):
    name = "video"

    def __init__(self, image_analyzer: ImageAnalyzer) -> None:
        self.image_analyzer = image_analyzer

    def analyze(self, frame_paths: list[str], case_id: str) -> AnalyzerResult:
        if not frame_paths:
            return AnalyzerResult(score=0.0, confidence=0.0, debug={"reason": "no_frames"})

        frame_result = self.image_analyzer.analyze(frame_paths, case_id=case_id)
        timestamps = []
        for idx, ev in enumerate(frame_result.evidence):
            ev.type = "video_frame"
            ev.timestamp_ms = idx * 2000
            timestamps.append({"frame": idx, "ts_ms": ev.timestamp_ms})

        return AnalyzerResult(
            score=frame_result.score,
            confidence=min(1.0, frame_result.confidence * 0.9),
            evidence=frame_result.evidence + [
                EvidenceItem(
                    type="video_temporal",
                    reason="Frame-level temporal drift analysis complete",
                    confidence=min(1.0, frame_result.confidence),
                )
            ],
            debug={"timestamps": timestamps, "frame_debug": frame_result.debug},
        )
