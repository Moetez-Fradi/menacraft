from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from app.shared.config import settings
from app.shared.schemas import LLMMessage

logger = logging.getLogger(__name__)


class OllamaLLMClient:
    def __init__(self) -> None:
        self.model = settings.ollama_model
        self.url = settings.ollama_base_url
        self.timeout = settings.ollama_timeout_seconds
        self.retries = settings.ollama_retries

    def is_configured(self) -> bool:
        return bool(self.model and self.url)

    def chat_json(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("OLLAMA_MODEL or OLLAMA_BASE_URL is missing")

        payload = {
            "model": model_override or self.model,
            "messages": [m.model_dump() for m in messages],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = requests.post(
                    self.url,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                body = response.json()
                content = (
                    body.get("message", {})
                    .get("content", "")
                )
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    repair_messages = messages + [
                        LLMMessage(
                            role="user",
                            content="Return valid strict JSON only. Do not include markdown fences.",
                        )
                    ]
                    payload["messages"] = [m.model_dump() for m in repair_messages]
                    continue
            except Exception as exc:
                last_error = exc
                logger.warning("Ollama call failed: %s (attempt %s)", exc, attempt + 1)
                if attempt < self.retries:
                    time.sleep(0.8 * (attempt + 1))
                continue

        raise RuntimeError(f"Ollama request failed: {last_error}")
