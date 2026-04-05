from __future__ import annotations

from enum import Enum


class Verdict(str, Enum):
    LIKELY_AUTHENTIC = "likely_authentic"
    UNCERTAIN = "uncertain"
    LIKELY_MANIPULATED = "likely_manipulated"
    LIKELY_AI_GENERATED = "likely_ai_generated"


class ContextVerdict(str, Enum):
    CONSISTENT = "consistent"
    UNCERTAIN = "uncertain"
    LIKELY_MISCONTEXTED = "likely_miscontexted"


TEXT_EMBEDDINGS_COLLECTION = "text_embeddings"
IMAGE_EMBEDDINGS_COLLECTION = "image_embeddings"
FRAME_EMBEDDINGS_COLLECTION = "frame_embeddings"
CASE_EMBEDDINGS_COLLECTION = "case_embeddings"
AUDIO_EMBEDDINGS_COLLECTION = "audio_embeddings"
