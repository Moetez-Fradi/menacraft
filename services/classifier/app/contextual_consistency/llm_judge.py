from __future__ import annotations

from app.clients.ollama_client import OllamaLLMClient
from app.shared.schemas import LLMMessage


class LLMJudge:
    def __init__(self, client: OllamaLLMClient) -> None:
        self.client = client

    def judge(self, claim_text: str, evidence_summary: dict[str, object]) -> dict[str, object]:
        if not self.client.is_configured():
            return {
                "error": "ollama_not_configured",
                "consistency_score": 0.5,
                "confidence": 0.0,
                "short_explanation": "LLM judge unavailable: OLLAMA_MODEL or OLLAMA_BASE_URL is missing.",
                "suspicious_parts": [],
                "reused_context": False,
            }

        prompt = (
            "Evaluate contextual consistency of a claim against evidence. "
            "Return strict JSON keys: consistency_score, confidence, short_explanation, suspicious_parts, reused_context.\n"
            f"Claim: {claim_text}\nEvidence: {evidence_summary}"
        )
        return self.client.chat_json(
            [
                LLMMessage(role="system", content="You are a strict contextual consistency judge. Return JSON only."),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=0.0,
        )
