from __future__ import annotations

import subprocess
from pathlib import Path


def run_ffmpeg(args: list[str]) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["ffmpeg", *args],
            check=False,
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0, (proc.stderr or proc.stdout)
    except FileNotFoundError:
        return False, "ffmpeg is not installed"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
