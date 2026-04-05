from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.clients.ollama_client import OllamaLLMClient
from app.shared.schemas import LLMMessage


@patch("app.clients.ollama_client.requests.post")
def test_ollama_client_parses_json(mock_post: Mock):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "message": {"content": '{"ai_probability": 0.83, "confidence": 0.91}'}
    }
    mock_post.return_value = response

    client = OllamaLLMClient()
    client.model = "llama3.1:8b"
    client.url = "http://localhost:11434/api/chat"

    out = client.chat_json([LLMMessage(role="user", content="x")])

    assert out["ai_probability"] == 0.83
    assert out["confidence"] == 0.91


def test_ollama_requires_model_and_url():
    client = OllamaLLMClient()
    client.model = ""
    with pytest.raises(RuntimeError):
        client.chat_json([])
