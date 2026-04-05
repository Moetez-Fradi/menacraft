from __future__ import annotations

import base64
from pathlib import Path

from app.shared.config import settings
from app.shared.hashing import sha256_file
from app.shared.media_utils import ensure_dir


class LocalStorage:
    def __init__(self, root_dir: str | None = None) -> None:
        self.root = Path(root_dir or settings.data_dir)
        ensure_dir(self.root)

    def case_dir(self, case_id: str) -> Path:
        path = self.root / "cases" / case_id
        ensure_dir(path)
        return path

    def write_text(self, case_id: str, name: str, text: str) -> Path:
        path = self.case_dir(case_id) / name
        path.write_text(text, encoding="utf-8")
        return path

    def write_bytes(self, case_id: str, name: str, data: bytes) -> Path:
        path = self.case_dir(case_id) / name
        path.write_bytes(data)
        return path

    def write_base64(self, case_id: str, name: str, encoded: str) -> Path:
        raw = base64.b64decode(encoded)
        return self.write_bytes(case_id, name, raw)

    def hash_path(self, path: Path) -> str:
        return sha256_file(path)
