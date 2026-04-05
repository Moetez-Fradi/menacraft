from __future__ import annotations

from app.embedders.embeddings import EmbedderService


class EntailmentScorer:
    def __init__(self, embedder: EmbedderService) -> None:
        self.embedder = embedder

    def score(self, claim_text: str, evidence_summary_text: str) -> dict[str, float | str]:
        v1 = self.embedder.embed_text(claim_text)
        v2 = self.embedder.embed_text(evidence_summary_text)
        dot = sum(a * b for a, b in zip(v1, v2))

        if dot >= 0.70:
            label = "entailment"
        elif dot <= 0.35:
            label = "contradiction"
        else:
            label = "neutral"

        return {
            "label": label,
            "score": max(0.0, min(1.0, float((dot + 1) / 2))),
        }
