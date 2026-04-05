from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from typing import Sequence

import numpy as np
from PIL import Image

from app.shared.config import settings

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def _text_model() -> Any:
    logger.info("Loading embedding model: %s", settings.embedding_model_name)
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("sentence-transformers is not installed") from exc
    return SentenceTransformer(settings.embedding_model_name, device="cpu")


class EmbedderService:
    def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            return [0.0] * 16
        vector = _text_model().encode([text], normalize_embeddings=True)[0]
        return vector.tolist()

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        cleaned = [t if t.strip() else " " for t in texts]
        matrix = _text_model().encode(cleaned, normalize_embeddings=True)
        return matrix.tolist()

    def embed_image(self, image: Image.Image) -> list[float]:
        arr = np.array(image.convert("RGB").resize((64, 64)), dtype=np.float32)
        hist = []
        for channel in range(3):
            values, _ = np.histogram(arr[:, :, channel], bins=16, range=(0, 255), density=True)
            hist.extend(values.tolist())
        norm = np.linalg.norm(hist) + 1e-9
        return (np.array(hist) / norm).tolist()
