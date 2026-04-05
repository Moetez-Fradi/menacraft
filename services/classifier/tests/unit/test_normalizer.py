from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image

from app.normalizers.case_normalizer import CaseNormalizer
from app.shared.schemas import CaseInput
from app.shared.storage import LocalStorage


def test_normalizer_creates_artifacts(tmp_path):
    storage = LocalStorage(str(tmp_path / "data"))
    normalizer = CaseNormalizer(storage)

    img = Image.new("RGB", (64, 64), color=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    case_input = CaseInput(
        session_id="case-123",
        text="Hello world",
        image_base64=b64,
        content_type="image",
        metadata={"platform": "test"},
    )

    artifacts = normalizer.normalize(case_input)

    assert artifacts.case_id == "case-123"
    assert artifacts.normalized_text == "Hello world"
    assert len(artifacts.image_artifacts) == 1
    assert "normalized_image" in artifacts.paths
