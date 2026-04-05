"""
Centralised configuration — loaded from environment variables.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


# ── LLM / OpenRouter settings ──────────────────────────────────────────────

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)
OPENROUTER_MODEL: str = os.getenv(
    "OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free"
)

# Toggle: set to "0" or "false" to disable LLM-based writing-style analysis
LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "true").lower() in ("1", "true", "yes")

# ── Scoring weights ─────────────────────────────────────────────────────────

WEIGHT_ACCOUNT_SIGNAL: float = float(os.getenv("WEIGHT_ACCOUNT_SIGNAL", "0.2"))
WEIGHT_SUSPICIOUS_DOMAIN: float = float(os.getenv("WEIGHT_SUSPICIOUS_DOMAIN", "0.3"))
WEIGHT_WRITING_STYLE: float = float(os.getenv("WEIGHT_WRITING_STYLE", "0.2"))

# ── Domain reputation cache TTL (seconds) ──────────────────────────────────

DOMAIN_CACHE_TTL: int = int(os.getenv("DOMAIN_CACHE_TTL", "3600"))
DOMAIN_CACHE_MAX_SIZE: int = int(os.getenv("DOMAIN_CACHE_MAX_SIZE", "2048"))

# ── Server ──────────────────────────────────────────────────────────────────

SERVICE_HOST: str = os.getenv("SERVICE_HOST", "0.0.0.0")
SERVICE_PORT: int = int(os.getenv("SERVICE_PORT", "8084"))
