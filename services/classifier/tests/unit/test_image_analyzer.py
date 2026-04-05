from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.analyzers.image_analyzer import ImageAnalyzer


class _StubEmbedder:
    def embed_image(self, image: Image.Image) -> list[float]:
        return [0.1, 0.2, 0.3, 0.4]


class _StubQdrant:
    def upsert_vector(self, collection: str, point_id: int, vector: list[float], payload: dict[str, object]) -> None:
        return None

    def search(self, collection: str, query_vector: list[float], limit: int = 3) -> list[dict[str, object]]:
        return [{"artifact_id": "x", "similarity": 0.31, "payload": {}}]


class _VisionLLMOk:
    def is_configured(self) -> bool:
        return True

    def chat_json(self, *args, **kwargs):
        return {
            "ai_generated_probability": 0.86,
            "manipulation_probability": 0.74,
            "authenticity_probability": 0.11,
            "confidence": 0.88,
            "verdict": "likely_ai_or_manipulated",
            "rationale": "Synthetic skin texture and inconsistent shadow transitions.",
            "suspicious_regions": [
                {"x": 0.31, "y": 0.22, "width": 0.18, "height": 0.2, "reason": "texture repetition"}
            ],
        }


class _VisionLLMUnavailable:
    def is_configured(self) -> bool:
        return False


def _create_image(path: Path) -> None:
    img = Image.new("RGB", (256, 256), color=(220, 80, 80))
    img.save(path)


def test_image_analyzer_uses_vision_llm_when_available(tmp_path: Path):
    image_path = tmp_path / "sample.jpg"
    _create_image(image_path)

    analyzer = ImageAnalyzer(embedder=_StubEmbedder(), qdrant=_StubQdrant(), llm_client=_VisionLLMOk())
    result = analyzer.analyze([str(image_path)], case_id="case-vision")

    assert result.debug["ai_feature_status"] == "ok"
    assert result.debug["llm_used"] is True
    assert result.debug["llm_success_count"] == 1
    assert result.score > 0.0
    assert result.confidence > 0.0
    assert len(result.debug["items"]) == 1
    assert result.debug["items"][0]["llm"]["status"] == "ok"


def test_image_analyzer_reports_unavailable_when_vision_not_configured(tmp_path: Path):
    image_path = tmp_path / "sample.jpg"
    _create_image(image_path)

    analyzer = ImageAnalyzer(embedder=_StubEmbedder(), qdrant=_StubQdrant(), llm_client=_VisionLLMUnavailable())
    result = analyzer.analyze([str(image_path)], case_id="case-no-vision")

    assert result.debug["ai_feature_status"] == "unavailable"
    assert result.debug["llm_used"] is False
    assert result.debug["llm_success_count"] == 0
    assert len(result.debug["errors"]) == 1
    assert result.debug["items"][0]["llm"]["status"] == "unavailable"