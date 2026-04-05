from __future__ import annotations

from typing import Any

import requests

from app.shared.config import settings


class QdrantHTTPSimilaritySearch:
    def __init__(self) -> None:
        self.base_url = settings.qdrant_url.rstrip("/")
        self.api_key = settings.qdrant_api_key
        self.enabled = settings.qdrant_http_similarity_enabled
        self.timeout = settings.qdrant_http_similarity_timeout_seconds

    def search_similar_image(
        self,
        collection: str,
        query_vector: list[float],
        *,
        limit: int = 6,
        exclude_case_id: str | None = None,
        exclude_artifact_id: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled or not query_vector:
            return None

        rows = self._run_search(collection=collection, query_vector=query_vector, limit=limit)
        if not rows:
            return None

        filtered: list[dict[str, Any]] = []
        for row in rows:
            payload_raw = row.get("payload")
            payload: dict[str, Any] = payload_raw if isinstance(payload_raw, dict) else {}
            artifact_id = str(payload.get("artifact_id") or row.get("id") or "")
            case_id = str(payload.get("case_id") or "")

            if exclude_artifact_id and artifact_id == exclude_artifact_id:
                continue
            if exclude_case_id and case_id == exclude_case_id:
                continue

            filtered.append(
                {
                    "artifact_id": artifact_id,
                    "case_id": case_id,
                    "similarity": float(row.get("score", 0.0)),
                    "payload": payload,
                }
            )

        if not filtered:
            return None

        filtered.sort(key=lambda item: item["similarity"], reverse=True)
        best = filtered[0]

        return {
            **best,
            "why_similar": self._why_similar(best),
        }

    def _run_search(self, collection: str, query_vector: list[float], limit: int) -> list[dict[str, Any]]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key

        payload = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }

        search_url = f"{self.base_url}/collections/{collection}/points/search"
        response = requests.post(search_url, json=payload, headers=headers, timeout=self.timeout)

        if response.status_code == 404:
            query_payload = {
                "query": query_vector,
                "limit": limit,
                "with_payload": True,
                "with_vector": False,
            }
            query_url = f"{self.base_url}/collections/{collection}/points/query"
            response = requests.post(query_url, json=query_payload, headers=headers, timeout=self.timeout)

        response.raise_for_status()
        body = response.json()
        result = body.get("result", [])

        if isinstance(result, list):
            return [row for row in result if isinstance(row, dict)]

        if isinstance(result, dict):
            points = result.get("points", [])
            return [row for row in points if isinstance(row, dict)]

        return []

    def _why_similar(self, row: dict[str, Any]) -> str:
        payload_raw = row.get("payload")
        payload: dict[str, Any] = payload_raw if isinstance(payload_raw, dict) else {}

        for key in (
            "why_similar",
            "similarity_reason",
            "visual_similarity_reason",
            "explainability",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        similarity = float(row.get("similarity", 0.0))
        modality = str(payload.get("modality", "image"))
        model_name = str(payload.get("model_name", "embedding-model"))

        if similarity >= 0.985:
            confidence_phrase = "nearly identical"
        elif similarity >= 0.95:
            confidence_phrase = "highly similar"
        else:
            confidence_phrase = "semantically similar"

        return (
            f"Qdrant HTTP similarity search marked this {modality} match as {confidence_phrase} "
            f"(score={similarity:.3f}) under {model_name}, indicating closely aligned visual embedding patterns."
        )
