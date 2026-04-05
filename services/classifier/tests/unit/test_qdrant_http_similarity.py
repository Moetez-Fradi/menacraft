from __future__ import annotations

from unittest.mock import Mock, patch

from app.qdrant.http_similarity import QdrantHTTPSimilaritySearch


def test_http_qdrant_similarity_returns_reason_from_payload():
    with patch("app.qdrant.http_similarity.settings.qdrant_http_similarity_enabled", True):
        searcher = QdrantHTTPSimilaritySearch()

    response = Mock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "result": [
            {
                "id": "42",
                "score": 0.973,
                "payload": {
                    "artifact_id": "case-b:image:1",
                    "case_id": "case-b",
                    "why_similar": "Both images share the same skyline contour and lighting structure.",
                },
            }
        ]
    }

    with patch("app.qdrant.http_similarity.requests.post", return_value=response):
        result = searcher.search_similar_image(
            "image_embeddings",
            [0.1, 0.2, 0.3],
            exclude_case_id="case-a",
            exclude_artifact_id="case-a:image:0",
        )

    assert result is not None
    assert result["artifact_id"] == "case-b:image:1"
    assert result["similarity"] == 0.973
    assert "skyline contour" in result["why_similar"]


def test_http_qdrant_similarity_filters_current_case():
    with patch("app.qdrant.http_similarity.settings.qdrant_http_similarity_enabled", True):
        searcher = QdrantHTTPSimilaritySearch()

    response = Mock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "result": [
            {
                "id": "1",
                "score": 0.999,
                "payload": {
                    "artifact_id": "case-a:image:0",
                    "case_id": "case-a",
                },
            }
        ]
    }

    with patch("app.qdrant.http_similarity.requests.post", return_value=response):
        result = searcher.search_similar_image(
            "image_embeddings",
            [0.1, 0.2, 0.3],
            exclude_case_id="case-a",
            exclude_artifact_id="case-a:image:0",
        )

    assert result is None
