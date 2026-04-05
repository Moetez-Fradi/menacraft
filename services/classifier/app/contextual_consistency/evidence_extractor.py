from __future__ import annotations

from app.shared.schemas import NormalizedArtifacts


class EvidenceExtractor:
    def extract_summary(self, artifacts: NormalizedArtifacts) -> dict[str, object]:
        return {
            "text": artifacts.normalized_text,
            "ocr_text": artifacts.ocr_text,
            "transcripts": artifacts.transcripts,
            "image_count": len(artifacts.image_artifacts),
            "frame_count": len(artifacts.video_frame_artifacts),
            "audio_count": len(artifacts.audio_artifacts),
            "metadata": artifacts.source_metadata,
            "technical": artifacts.technical_metadata,
        }
