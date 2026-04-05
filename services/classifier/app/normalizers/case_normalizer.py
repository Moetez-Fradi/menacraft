from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from PIL import Image

from app.shared.hashing import sha256_bytes
from app.shared.schemas import CaseInput, MediaArtifact, NormalizedArtifacts
from app.shared.storage import LocalStorage
from app.shared.text_utils import clean_text

logger = logging.getLogger(__name__)


class CaseNormalizer:
    def __init__(self, storage: LocalStorage) -> None:
        self.storage = storage

    def normalize(self, case_input: CaseInput, case_id: str | None = None) -> NormalizedArtifacts:
        resolved_case_id = case_id or case_input.session_id or str(uuid.uuid4())

        cleaned_text = clean_text(case_input.clean_text or case_input.text or "")
        paths: dict[str, str] = {}
        hashes: dict[str, str] = {}
        image_artifacts: list[MediaArtifact] = []

        raw_payload = case_input.model_dump()
        payload_path = self.storage.write_text(resolved_case_id, "input_payload.json", json.dumps(raw_payload, indent=2))
        paths["input_payload"] = str(payload_path)

        if cleaned_text:
            text_path = self.storage.write_text(resolved_case_id, "normalized_text.txt", cleaned_text)
            paths["normalized_text"] = str(text_path)
            hashes["normalized_text_sha256"] = sha256_bytes(cleaned_text.encode("utf-8"))

        image_b64 = case_input.clean_image_base64 or case_input.image_base64
        if image_b64:
            raw_path = self.storage.write_base64(resolved_case_id, "input_image.bin", image_b64)
            hashes["input_image_sha256"] = self.storage.hash_path(raw_path)

            img = Image.open(raw_path).convert("RGB")
            normalized_img_path = self.storage.case_dir(resolved_case_id) / "normalized_image.jpg"
            img.thumbnail((1280, 1280))
            img.save(normalized_img_path, format="JPEG", quality=92)
            paths["normalized_image"] = str(normalized_img_path)
            hashes["normalized_image_sha256"] = self.storage.hash_path(normalized_img_path)

            image_artifacts.append(
                MediaArtifact(
                    artifact_id=f"{resolved_case_id}:image:0",
                    modality="image",
                    path=str(normalized_img_path),
                    hash_sha256=hashes["normalized_image_sha256"],
                    metadata={"source": "upload"},
                )
            )

        return NormalizedArtifacts(
            case_id=resolved_case_id,
            source_metadata=case_input.metadata,
            normalized_text=cleaned_text,
            image_artifacts=image_artifacts,
            video_frame_artifacts=[],
            audio_artifacts=[],
            transcripts=[],
            ocr_text=[],
            technical_metadata={"content_type": case_input.content_type},
            hashes=hashes,
            paths=paths,
        )
