from __future__ import annotations

from typing import Any

from app.shared.config import settings


class QdrantEvidenceStore:
    def __init__(self) -> None:
        self.enabled = settings.qdrant_enabled
        self.client: Any | None = None
        if self.enabled:
            from qdrant_client import QdrantClient

            self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    def ensure_collection(self, name: str, size: int) -> None:
        if not self.client:
            return
        from qdrant_client.http.models import Distance, VectorParams

        collections = {c.name for c in self.client.get_collections().collections}
        if name not in collections:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=size, distance=Distance.COSINE),
            )

    def upsert_vector(self, collection: str, point_id: int, vector: list[float], payload: dict[str, Any]) -> None:
        if not self.client:
            return
        from qdrant_client.http.models import PointStruct

        self.ensure_collection(collection, len(vector))
        self.client.upsert(
            collection_name=collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    def search(self, collection: str, query_vector: list[float], limit: int = 5) -> list[dict[str, Any]]:
        if not self.client:
            return []
        self.ensure_collection(collection, len(query_vector))
        results = self.client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
        )
        return [
            {
                "artifact_id": str(item.id),
                "similarity": float(item.score),
                "payload": item.payload or {},
            }
            for item in results
        ]
