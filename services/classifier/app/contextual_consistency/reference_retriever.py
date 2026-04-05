from __future__ import annotations

from app.embedders.embeddings import EmbedderService
from app.qdrant.store import QdrantEvidenceStore
from app.shared.constants import CASE_EMBEDDINGS_COLLECTION, FRAME_EMBEDDINGS_COLLECTION, IMAGE_EMBEDDINGS_COLLECTION, TEXT_EMBEDDINGS_COLLECTION
from app.shared.schemas import RetrievalResult


class ReferenceRetriever:
    def __init__(self, embedder: EmbedderService, qdrant: QdrantEvidenceStore) -> None:
        self.embedder = embedder
        self.qdrant = qdrant

    def retrieve(self, claim_text: str, limit: int = 5) -> list[RetrievalResult]:
        vector = self.embedder.embed_text(claim_text)
        items: list[RetrievalResult] = []

        for collection in [TEXT_EMBEDDINGS_COLLECTION, IMAGE_EMBEDDINGS_COLLECTION, FRAME_EMBEDDINGS_COLLECTION, CASE_EMBEDDINGS_COLLECTION]:
            for row in self.qdrant.search(collection, query_vector=vector, limit=limit):
                payload = row.get("payload", {})
                items.append(
                    RetrievalResult(
                        artifact_id=str(payload.get("artifact_id", row["artifact_id"])),
                        similarity=float(row["similarity"]),
                        label=payload.get("label"),
                        modality=str(payload.get("modality", "unknown")),
                        explanation=str(payload.get("explainability", "Similarity-based retrieval match")),
                        payload=payload,
                    )
                )

        items.sort(key=lambda x: x.similarity, reverse=True)
        return items[:limit]
